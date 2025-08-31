import asyncio
import json
import time
import uuid
import struct
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
from internal.infra.log.logger import logger
from internal.domain.enum import WebSocketMessageType, WebSocketErrorCode
from internal.domain.models.websocket import ErrorMessage, AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage
from internal.infra.websocket.server_callback import WebSocketServerCallback

class WebSocketServer:
    def __init__(self):
        self.active_connections: Dict[str, WebSocketClient] = {}
        self.user_sessions: Dict[str, Set[str]] = {}
        self.callbacks = WebSocketServerCallback()

    async def connect(self, websocket: WebSocket, params: dict) -> WebSocketClient:
        user_id = params["user_id"]
        session_id = params["session_id"]
        language = params["language"]
        
        logger.info(f"[Websocket: connect] {user_id} {session_id} {language}")
        if session_id in self.active_connections:
            await self.disconnect(self.active_connections[session_id])
        await websocket.accept()
        
        client = WebSocketClient(websocket, user_id, session_id, language=language)
        self.active_connections[session_id] = client
        self.user_sessions.setdefault(user_id, set()).add(session_id)
        
        logger.info(f"[Websocket: connect successful] {user_id} {session_id}")
        await self._send_json(client, {"type": WebSocketMessageType.CONNECTION_ESTABLISHED, "session_id": session_id})
        return client

    async def serve(self, client: WebSocketClient):
        logger.info(f"[Websocket: serve] {client.user_id} {client.session_id}")
        read_task = asyncio.create_task(self._read_loop(client))
        
        try:
            await asyncio.wait({read_task}, return_when=asyncio.FIRST_COMPLETED)
            
        except asyncio.CancelledError:
            logger.info(f"[Websocket: serve] {client.user_id} {client.session_id}: cancelled")
            await self.disconnect(client)
            
        except Exception as e:
            logger.error(f"[Websocket: serve] {client.user_id} {client.session_id}: {e}")
            await self.disconnect(client)
            
        finally:
            for t in (read_task):
                if not t.done():
                    t.cancel()
            await self.disconnect(client)

    async def _read_loop(self, client: WebSocketClient):
        logger.info(f"[Websocket: read_loop] {client.user_id} {client.session_id}")
        try:
            while client.is_connected:
                message = await client.websocket.receive()
                
                if message["type"] == "websocket.disconnect":
                    break
                
                await self._handle_message(client, message)
                    
        except WebSocketDisconnect:
            logger.info(f"WS disconnect from {client.user_id}")
            
        except Exception as e:
            logger.error(f"Read error from {client.user_id}: {e}")
            
        finally:
            await self.disconnect(client)

    async def disconnect(self, client: WebSocketClient):
        if not client.is_connected:
            return
        client.is_connected = False

        self.active_connections.pop(client.session_id, None)
        user_sessions = self.user_sessions.get(client.user_id)
        if user_sessions:
            user_sessions.discard(client.session_id)
            if not user_sessions:
                self.user_sessions.pop(client.user_id, None)

        try:
            await client.websocket.close()
            
        except Exception as e:
            logger.error(f"Error closing WS for {client.user_id}: {e}")

        logger.info(f"Disconnected {client.user_id} from {client.session_id}")

    async def _handle_message(self, client: WebSocketClient, message: dict):
        logger.info(f"[Websocket: handle message] Called")
        try:
            content = message.get("bytes") or message.get("text", "")
            if isinstance(content, bytes):
                await self._handle_audio_message(client, content)
            else:
                await self._handle_text_message(client, content)
                
        except Exception as e:
            logger.error(f"Handle error for {client.user_id}: {e}")
            await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, str(e))

    def _validate_segment_message(self, data: dict, expected_type: str) -> tuple[bool, str]:
        required_fields = ["type", "session_id", "segment_id"]

        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"

        if data["type"] != expected_type:
            return False, f"Invalid message type: expected {expected_type}, got {data['type']}"

        return True, ""

    def _create_segment_start_message(self, data: dict) -> SegmentStartMessage:
        return SegmentStartMessage(
            type=data["type"],
            session_id=data["session_id"],
            segment_id=data["segment_id"]
        )

    def _create_segment_end_message(self, data: dict) -> SegmentEndMessage:
        return SegmentEndMessage(
            type=data["type"],
            session_id=data["session_id"],
            segment_id=data["segment_id"]
        )

    async def _handle_text_message(self, client: WebSocketClient, content: str):
        logger.info(f"[Websocket: handle text message]: Called")
        try:
            logger.info(f"[Websocket: handle text message inside loop]: {content}")
            data = json.loads(content)
            t = data.get("type")

            match t:
                case WebSocketMessageType.SEGMENT_START:
                    is_valid, error_msg = self._validate_segment_message(data, WebSocketMessageType.SEGMENT_START)
                    if not is_valid:
                        await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, error_msg)
                        return

                    segment_start_msg = self._create_segment_start_message(data)
                    await self.callbacks.handle_segment_start(client, segment_start_msg)

                case WebSocketMessageType.SEGMENT_END:
                    is_valid, error_msg = self._validate_segment_message(data, WebSocketMessageType.SEGMENT_END)
                    if not is_valid:
                        await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, error_msg)
                        return

                    segment_end_msg = self._create_segment_end_message(data)
                    await self.callbacks.handle_segment_end(client, segment_end_msg)

                case _:
                    await self._send_json(client, {"type": WebSocketMessageType.ECHO, "content": data})
                    
        except json.JSONDecodeError:
            await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, "Invalid JSON")
            
        except Exception as e:
            await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, str(e))

    async def _handle_audio_message(self, client: WebSocketClient, content: bytes):
        logger.info(f"[Websocket: handle audio message]: Called")
        
        try:
            if len(content) < 4:
                await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, "Audio message too short")
                return
            
            header_length = struct.unpack('>I', content[:4])[0]

            # Validate header length to prevent reading corrupted data
            if header_length <= 0:
                await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, "Invalid header length: must be positive")
                return
            if header_length > 10000:  # Reasonable upper bound for JSON header
                await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, f"Header length too large: {header_length} bytes")
                return

            if len(content) < 4 + header_length:
                await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, "Audio message incomplete")
                return
            
            header_bytes = content[4:4 + header_length]
            try:
                header = json.loads(header_bytes.decode('utf-8'))
            except UnicodeDecodeError as e:
                logger.error(f"[Websocket: handle audio message] UTF-8 decode error at position {e.start}: byte 0x{e.object[e.start]:02x} in header")
                logger.error(f"[Websocket: handle audio message] Header length: {header_length}, Total message length: {len(content)}")
                logger.error(f"[Websocket: handle audio message] Header bytes (first 100): {header_bytes[:100] if len(header_bytes) > 0 else 'empty'}")
                await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, f"Invalid UTF-8 in header at position {e.start}")
                return
            except json.JSONDecodeError as e:
                logger.error(f"[Websocket: handle audio message] JSON decode error: {e}")
                logger.error(f"[Websocket: handle audio message] Header bytes as string: {header_bytes[:200].decode('utf-8', errors='replace') if len(header_bytes) > 0 else 'empty'}")
                await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, f"Invalid header JSON: {e}")
                return
            
            audio_data = content[4 + header_length:]
            
            msg_type = header.get("type")
            session_id = header.get("session_id")
            segment_id = header.get("segment_id")
            
            if not all([msg_type, session_id, segment_id]):
                await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, "Missing required header fields")
                return
            
            if client.session_id != session_id:
                await self._send_error(client, WebSocketErrorCode.SESSION_ID_MISMATCH, "Session ID mismatch")
                return
            

            req = AudioChunkMessage(
                type=msg_type,
                segment_id=segment_id,
                audio_data=audio_data,
            )
            await self.callbacks.handle_audio_chunk(client, req)
            
        except Exception as e:
            logger.error(f"Error handling audio message from {client.user_id}: {e}")
            await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, str(e))

    async def _send_json(self, client: WebSocketClient, data: dict):
        try:
            if client.is_connected:
                await client.websocket.send_text(json.dumps(data))
                
        except Exception as e:
            logger.error(f"Send error to {client.user_id}: {e}")
            await self.disconnect(client)

    async def _send_error(self, client: WebSocketClient, code: str, message: str):
        await self._send_json(client, ErrorMessage(code=code, message=message).__dict__)


ws_server = WebSocketServer()
