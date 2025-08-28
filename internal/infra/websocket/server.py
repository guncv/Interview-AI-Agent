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

class WebSocketServer:
    def __init__(self):
        self.active_connections: Dict[str, WebSocketClient] = {}
        self.user_sessions: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, session_id: str) -> WebSocketClient:
        logger.info(f"[Websocket: connect] {user_id} {session_id}")
        if session_id in self.active_connections:
            await self.disconnect(self.active_connections[session_id])
        await websocket.accept()
        
        client = WebSocketClient(websocket, user_id, session_id)
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
        logger.info(f"[Websocket: read_loop] {client.user_id} {client.session_id}, {client.is_connected}")
        try:
            while client.is_connected:
                message = await client.websocket.receive()
                logger.info(f"[Websocket: read loop get message] {message}")
                
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
        logger.info(f"[Websocket: handle message] {client.user_id} {client.session_id}, {message}")
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
        logger.info(f"[Websocket: handle text message] {client.user_id} {client.session_id}, {content}")
        try:
            data = json.loads(content)
            t = data.get("type")

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
