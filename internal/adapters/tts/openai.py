import asyncio
import aiohttp
from typing import AsyncGenerator, Dict, Optional
from internal.adapters.log.logger import logger
from internal.config.config import nested_config as config
from internal.domain.ports.tts_port import TTSPort

class OpenAITTS(TTSPort):
    def __init__(self):
        self.api_key = config["tts"]["openai_api_key"]
        self.model = "gpt-4o-mini-tts"
        self.voice = config["tts"].get("voice", "nova")
        self.url = "https://api.openai.com/v1/audio/speech"

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        logger.info(f"[OpenAI TTS REST] Synthesizing stream for text: {text[:50]}...")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": "opus"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error_msg = await resp.text()
                        logger.error(f"[OpenAI TTS REST] Error {resp.status}: {error_msg}")
                        raise RuntimeError(f"TTS request failed: {error_msg}")

                    logger.info(f"[OpenAI TTS REST] Streaming audio for text: {text[:50]}...")
                    async for chunk in resp.content.iter_chunked(8192):
                        yield chunk
        except Exception as e:
            logger.exception(f"[OpenAI TTS REST] Unexpected error: {e}")
            raise
