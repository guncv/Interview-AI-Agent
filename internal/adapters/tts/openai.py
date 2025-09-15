import asyncio
import websockets
import json
import base64
from typing import AsyncGenerator, Dict
from internal.adapters.log.logger import logger
from internal.config.config import nested_config as config
from internal.domain.ports.tts_port import TTSPort

class OpenAITTSSession(TTSPort):
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.api_key = config["tts"]["openai_api_key"]
        self.url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
        self.voice = config["tts"].get("voice", "verse")

        self.ws = None
        self._lock = asyncio.Lock()
        logger.info(f"[OpenAI TTS] Session {session_id} initialized with voice {self.voice}")

    async def connect(self):
        logger.info(f"[OpenAI TTS] Connecting for session {self.session_id}")
        self.ws = await websockets.connect(
            self.url,
            additional_headers={
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        )
        logger.info(f"[OpenAI TTS] Connected | Session {self.session_id}")

    async def close(self):
        if self.ws:
            await self.ws.close()
            logger.info(f"[OpenAI TTS] Closed connection | Session {self.session_id}")
            self.ws = None

    async def synthesize_stream(self, text: str, session_id: str) -> AsyncGenerator[bytes, None]:
        logger.info(f"[OpenAI TTS Session] Synthesizing stream Called: {session_id}")
        if session_id != self.session_id:
            raise ValueError(f"Session ID mismatch: expected {self.session_id}, got {session_id}")
        
        async for chunk in self.synthesize(text):
            logger.info(f"[OpenAI TTS Session] Synthesizing stream Yielding chunk: {session_id}")
            yield chunk

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        logger.info(f"[OpenAI TTS Session] Synthesizing stream Called: {self.session_id}")
        if not self.ws:
            raise RuntimeError("TTS WebSocket not connected")

        async with self._lock:
            request = {
                "type": "response.create",
                "response": {
                    "modalities": ["audio", "text"],
                    "instructions": text,
                    "voice": self.voice
                }
            }
            await self.ws.send(json.dumps(request))
            logger.debug(f"[OpenAI TTS] Sent text for synthesis | Session {self.session_id}")

            async for msg in self.ws:
                logger.info(f"[OpenAI TTS Session] Synthesizing stream Received message: {msg}")
                data = json.loads(msg)

                if data["type"] == "response.audio.delta":
                    audio_chunk = base64.b64decode(data["delta"])
                    logger.info(f"[OpenAI TTS Session] Yielding audio chunk of size {len(audio_chunk)} | Session {self.session_id}")
                    yield audio_chunk

                elif data["type"] == "response.audio.done":
                    logger.info(f"[OpenAI TTS Session] Audio generation completed | Session {self.session_id}")
                    break

                elif data["type"] == "response.done":
                    logger.info(f"[OpenAI TTS Session] Response completed | Session {self.session_id}")
                    break

                elif data["type"] == "error":
                    err_msg = data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"[OpenAI TTS Session] API error: {err_msg} | Session {self.session_id}")
                    raise RuntimeError(err_msg)


class OpenAITTS:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OpenAITTS, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.sessions: Dict[str, OpenAITTSSession] = {}
            logger.info("[OpenAI TTS] Service manager initialized")
            OpenAITTS._initialized = True

    async def get_session(self, session_id: str) -> OpenAITTSSession:
        if session_id not in self.sessions:
            session = OpenAITTSSession(session_id)
            await session.connect()
            self.sessions[session_id] = session
            logger.info(f"[OpenAI TTS] Created and connected new session: {session_id}")
        return self.sessions[session_id]

    async def close_session(self, session_id: str):
        if session_id in self.sessions:
            await self.sessions[session_id].close()
            del self.sessions[session_id]
            logger.info(f"[OpenAI TTS] Closed and removed session: {session_id}")

    async def synthesize_stream(self, text: str, session_id: str) -> AsyncGenerator[bytes, None]:
        logger.info(f"[OpenAI TTS] Synthesizing stream Called: {session_id}")
        session = await self.get_session(session_id)
        logger.info(f"[OpenAI TTS] Synthesizing stream Got session: {session_id}")
        async for chunk in session.synthesize_stream(text, session_id):
            logger.info(f"[OpenAI TTS] Synthesizing stream Yielding chunk: {session_id}")
            yield chunk

    async def close_all_sessions(self):
        for session_id in list(self.sessions.keys()):
            await self.close_session(session_id)
        logger.info("[OpenAI TTS] Closed all sessions")
