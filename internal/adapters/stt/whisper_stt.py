import io
import wave
from typing import List
from openai import OpenAI, OpenAIError
from internal.adapters.log.logger import logger
from internal.config.config import nested_config as config
from internal.domain.models.speech_recognize import SpeechRecognize, Word
from internal.domain.ports.stt_port import STTPort

class WhisperSpeechToText(STTPort):
    def __init__(self):
        self.api_key = config["stt"]["whisper_api_key"]
        self.client = OpenAI(api_key=self.api_key)
        self.model = "whisper-1"

    async def _wrap_wav_bytes(self, audio_bytes: bytes) -> io.BytesIO:
        logger.debug("[Whisper STT] Wrapping audio bytes into WAV format")
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)
        buffer.seek(0)
        buffer.name = "audio.wav"
        return buffer

    async def _clean_transcript(self, text: str) -> str:
        cleaned = text.strip()
        return cleaned[:-3].rstrip() if cleaned.endswith("...") else cleaned

    async def transcribe(self, audio_chunk: bytes, session_id: str) -> SpeechRecognize:
        logger.info(f"[Whisper STT] Transcribing audio | Session: {session_id}")

        try:
            audio_file = await self._wrap_wav_bytes(audio_chunk)

            response = self.client.audio.transcriptions.create(
                file=audio_file,
                model=self.model,
                response_format="verbose_json",
                language="en",
                timestamp_granularities=["word"]
            )

            logger.debug(f"[Whisper STT] API response: {response}")
            transcript = await self._clean_transcript(response.text)
            words: List[Word] = []

            if hasattr(response, "words") and response.words:
                words = [
                    Word(
                        word=w.word.strip(),
                        start=w.start,
                        end=w.end,
                        confidence=1.0
                    )
                    for w in response.words
                ]

            return SpeechRecognize(transcript=transcript, words=words)

        except OpenAIError as e:
            logger.exception(f"[Whisper STT] OpenAI API Error | Session: {session_id}")
            raise RuntimeError(f"Whisper STT failed: {e}") from e

        except Exception as e:
            logger.exception(f"[Whisper STT] Unexpected error | Session: {session_id}")
            raise
