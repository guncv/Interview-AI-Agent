import asyncio
import json
import time
import uuid
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
from internal.infra.log.logger import logger

class WebSocketMessageType(str, Enum):
    CONNECTION_ESTABLISHED = "connection_established"
    SEGMENT_START = "segment_start"
    SEGMENT_END = "segment_end"
    ERROR = "error"
    ECHO = "echo"
    PING = "ping"
    PONG = "pong"


class WebSocketErrorCode(str, Enum):
    INVALID_TOKEN = "invalid_token"
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_MESSAGE = "invalid_message"
    INVALID_SEGMENT_START = "invalid_segment_start"
    INVALID_SEGMENT_END = "invalid_segment_end"
    SESSION_ID_MISMATCH = "session_id_mismatch"
    SEGMENT_ID_MISMATCH = "segment_id_mismatch"


@dataclass
class WebSocketClient:
    websocket: WebSocket
    user_id: str
    session_id: str
    last_pong_time: float = field(default_factory=time.time)
    pong_received: asyncio.Event = field(default_factory=asyncio.Event)
    is_connected: bool = True
    current_segment_id: Optional[str] = None


@dataclass
class AudioChunkHeader:
    type: str
    session_id: str
    segment_id: str


@dataclass
class SegmentStartMessage:
    type: str
    session_id: str
    segment_id: str


@dataclass
class SegmentEndMessage:
    type: str
    session_id: str
    segment_id: str
    timestamp: Optional[float] = None


@dataclass
class ErrorMessage:
    type: str = "error"
    code: str = ""
    message: str = ""


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocketClient] = {}
        self.user_sessions: Dict[str, Set[str]] = {}
        self.ping_interval: float = 30.0
        self.pong_timeout: float = 10.0
        self.read_timeout: float = 60.0

    async def connect(self, websocket: WebSocket, user_id: str, session_id: str) -> WebSocketClient:
        logger.info(f"[Websocket: connect] {user_id} {session_id}")
        if session_id in self.active_connections:
            await self.disconnect(self.active_connections[session_id])
        await websocket.accept()
        
        logger.info(f"[Websocket: connect] {user_id} {session_id}")
        client = WebSocketClient(websocket, user_id, session_id)
        self.active_connections[session_id] = client
        self.user_sessions.setdefault(user_id, set()).add(session_id)
        
        logger.info(f"[Websocket: connect] {user_id} {session_id}")
        await self._send_json(client, {"type": WebSocketMessageType.CONNECTION_ESTABLISHED, "session_id": session_id})
        logger.info(f"[Websocket: connect] Client {user_id} connected to session {session_id}. Total: {len(self.active_connections)}")
        return client

    async def serve(self, client: WebSocketClient):
        logger.info(f"[Websocket: serve] {client.user_id} {client.session_id}")
        ping_task = asyncio.create_task(self._ping_loop(client))
        read_task = asyncio.create_task(self._read_loop(client))
        
        try:
            await asyncio.wait({ping_task, read_task}, return_when=asyncio.FIRST_COMPLETED)
            
        finally:
            for t in (ping_task, read_task):
                if not t.done():
                    t.cancel()
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

    async def _read_loop(self, client: WebSocketClient):
        try:
            while client.is_connected:
                try:
                    message = await asyncio.wait_for(client.websocket.receive(), timeout=self.read_timeout)
                    if message["type"] == "websocket.disconnect":
                        break
                    await self._handle_message(client, message)
                except asyncio.TimeoutError:
                    if time.time() - client.last_pong_time > self.pong_timeout:
                        logger.warning(f"Timeout from {client.user_id}")
                        break
                    
        except WebSocketDisconnect:
            logger.info(f"WS disconnect from {client.user_id}")
            
        except Exception as e:
            logger.error(f"Read error from {client.user_id}: {e}")
            
        finally:
            await self.disconnect(client)

    async def _handle_message(self, client: WebSocketClient, message: dict):
        try:
            content = message.get("bytes") or message.get("text", "")
            if isinstance(content, bytes):
                await self._handle_audio_message(client, content)
            else:
                await self._handle_text_message(client, content)
                
        except Exception as e:
            logger.error(f"Handle error for {client.user_id}: {e}")
            await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, str(e))

    async def _handle_text_message(self, client: WebSocketClient, content: str):
        try:
            data = json.loads(content)
            t = data.get("type")

            if t == WebSocketMessageType.PONG:
                client.last_pong_time = time.time()
                return

            if t == WebSocketMessageType.PING:
                await self._send_json(client, {"type": WebSocketMessageType.PONG, "timestamp": time.time()})
                return

            match t:
                case WebSocketMessageType.SEGMENT_START:
                    await self._handle_segment_start(client, data)
                case WebSocketMessageType.SEGMENT_END:
                    await self._handle_segment_end(client, data)
                case _:
                    await self._send_json(client, {"type": WebSocketMessageType.ECHO, "content": data})
                    
        except json.JSONDecodeError:
            await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, "Invalid JSON")
            
        except Exception as e:
            await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, str(e))

    async def _handle_segment_start(self, client: WebSocketClient, data: dict):
        try:
            msg = SegmentStartMessage(**data)
            if msg.session_id != client.session_id:
                await self._send_error(client, WebSocketErrorCode.SESSION_ID_MISMATCH, "Session mismatch")
                return
            client.current_segment_id = msg.segment_id
            
        except Exception as e:
            await self._send_error(client, WebSocketErrorCode.INVALID_SEGMENT_START, str(e))

    async def _handle_segment_end(self, client: WebSocketClient, data: dict):
        try:
            msg = SegmentEndMessage(**data)
            if msg.session_id != client.session_id:
                await self._send_error(client, WebSocketErrorCode.SESSION_ID_MISMATCH, "Session mismatch")
                return
            if msg.segment_id != client.current_segment_id:
                await self._send_error(client, WebSocketErrorCode.SEGMENT_ID_MISMATCH, "Segment mismatch")
                return
            client.current_segment_id = None
            
        except Exception as e:
            await self._send_error(client, WebSocketErrorCode.INVALID_SEGMENT_END, str(e))

    async def _handle_audio_message(self, client: WebSocketClient, audio_data: bytes):
        try:
            if len(audio_data) < 4:
                return
            header_len = int.from_bytes(audio_data[:4], 'big')
            if 4 + header_len > len(audio_data):
                return
            header_bytes = audio_data[4:4 + header_len]
            header = AudioChunkHeader(**json.loads(header_bytes.decode()))
            if header.session_id != client.session_id:
                await self._send_error(client, WebSocketErrorCode.SESSION_ID_MISMATCH, "Session mismatch")
                return
            if header.segment_id != client.current_segment_id:
                await self._send_error(client, WebSocketErrorCode.SEGMENT_ID_MISMATCH, "Segment mismatch")
                return
            
        except Exception as e:
            await self._send_error(client, WebSocketErrorCode.INVALID_MESSAGE, str(e))

    async def _ping_loop(self, client: WebSocketClient):
        try:
            while client.is_connected:
                await asyncio.sleep(self.ping_interval)
                if time.time() - client.last_pong_time > self.pong_timeout:
                    break
                await client.websocket.send_text(json.dumps({
                    "type": WebSocketMessageType.PING,
                    "timestamp": time.time()
                }))
                
        except Exception as e:
            logger.error(f"Ping error for {client.user_id}: {e}")
            
        finally:
            if client.is_connected:
                await self.disconnect(client)

    async def _send_json(self, client: WebSocketClient, data: dict):
        try:
            if client.is_connected:
                await client.websocket.send_text(json.dumps(data))
                
        except Exception as e:
            logger.error(f"Send error to {client.user_id}: {e}")
            await self.disconnect(client)

    async def _send_error(self, client: WebSocketClient, code: str, message: str):
        await self._send_json(client, ErrorMessage(code=code, message=message).__dict__)


manager = ConnectionManager()
