import asyncio
import websockets
import json
import base64
from typing import AsyncGenerator
from internal.domain.ports.tts_port import TTSPort
from internal.adapters.log.logger import logger
from internal.config.config import nested_config as config

class OpenAITTS(TTSPort):
    def __init__(self):
        self.api_key = config["tts"]["openai_api_key"]
        self.url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-tts"
        self.voice = config["tts"].get("voice", "verse")
        logger.info(f"[OpenAI TTS] Initialized with voice: {self.voice}")

    async def synthesize_stream(self, text: str, session_id: str) -> AsyncGenerator[bytes, None]:
        logger.info(f"[OpenAI TTS] Starting synthesis | Session: {session_id} | Text: '{text[:50]}...'")
        
        try:
            async with websockets.connect(
                self.url,
                extra_headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "OpenAI-Beta": "realtime=v1"
                }
            ) as ws:
                request = {
                    "type": "response.create",
                    "response": {
                        "modalities": ["audio"],
                        "instructions": text,
                        "voice": self.voice
                    }
                }
                
                await ws.send(json.dumps(request))
                logger.debug(f"[OpenAI TTS] Sent synthesis request | Session: {session_id}")

                async for msg in ws:
                    try:
                        data = json.loads(msg)
                        
                        if data["type"] == "response.output_audio.delta":
                            audio_chunk = base64.b64decode(data["delta"])
                            logger.debug(f"[OpenAI TTS] Got audio chunk: {len(audio_chunk)} bytes | Session: {session_id}")
                            yield audio_chunk
                            
                        elif data["type"] == "response.completed":
                            logger.info(f"[OpenAI TTS] Synthesis completed | Session: {session_id}")
                            break
                            
                        elif data["type"] == "error":
                            error_msg = data.get("error", {}).get("message", "Unknown error")
                            logger.error(f"[OpenAI TTS] API Error: {error_msg} | Session: {session_id}")
                            raise RuntimeError(f"OpenAI TTS API error: {error_msg}")
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"[OpenAI TTS] Failed to parse message: {e} | Session: {session_id}")
                        continue
                        
        except websockets.exceptions.WebSocketException as e:
            logger.exception(f"[OpenAI TTS] WebSocket error | Session: {session_id}")
            raise RuntimeError(f"OpenAI TTS connection failed: {e}") from e
            
        except Exception as e:
            logger.exception(f"[OpenAI TTS] Unexpected error | Session: {session_id}")
            raise
