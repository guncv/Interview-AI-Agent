import os
import io
import tempfile
import subprocess
from typing import List

from openai import OpenAI, OpenAIError
from internal.adapters.log.logger import logger
from internal.config.config import nested_config as config
from internal.domain.models.speech_recognize import SpeechRecognize, Word
from internal.domain.ports.stt_port import STTPort
from internal.adapters.db.redis import redis_client


class WhisperSpeechToText(STTPort):
    def __init__(self):
        self.api_key = config["stt"]["whisper_api_key"]
        self.client = OpenAI(api_key=self.api_key)
        self.model = "whisper-1"

    async def transcribe(self, audio_chunk: bytes, session_id: str, bias_prompt: str) -> SpeechRecognize:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = os.path.join(tmpdir, "input.webm")
                output_path = os.path.join(tmpdir, "output.wav")

                with open(input_path, "wb") as f:
                    f.write(audio_chunk)
 
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", input_path,
                    "-ac", "1",
                    "-ar", "16000",
                    "-f", "wav",
                    output_path
                ]
                proc = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if proc.returncode != 0:
                    logger.error(f"[FFmpeg Error] {proc.stderr.decode()}")
                    raise RuntimeError("FFmpeg failed to convert WebM to WAV")

                with open(output_path, "rb") as f:
                    wav_buffer = io.BytesIO(f.read())
                    wav_buffer.name = "audio.wav"
            
            if bias_prompt:
                if len(bias_prompt) > 896:
                    bias_prompt = bias_prompt[:896]
            
            response = self.client.audio.transcriptions.create(
                file=wav_buffer,
                model=self.model,
                response_format="verbose_json",
                language="en",
                timestamp_granularities=["word"],
                prompt=bias_prompt
            )

            logger.debug(f"[Whisper STT] API response: {response}")

            raw_text = response.text.strip()
            transcript = raw_text[:-3].rstrip() if raw_text.endswith("...") else raw_text

            words: List[Word] = []
            if hasattr(response, "words") and response.words:
                words = [
                    Word(
                        word=w.word.strip(),
                        start=w.start,
                        end=w.end,
                        confidence=getattr(w, "confidence", 1.0) or 1.0
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
