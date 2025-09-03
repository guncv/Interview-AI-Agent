import tempfile
import os
import io
import struct
import wave
from typing import Optional, List
from internal.infra.log.logger import logger
from internal.domain.models.speech_recognize import SpeechRecognize, Word
from openai import OpenAI
from internal.config.config import nested_config as config

class WhisperSpeechToText:

    def __init__(self):
        self.api_key = config["stt"]["whisper_api_key"]
        self.client = OpenAI(api_key=self.api_key)
        self.model = "whisper-1"
        
    def _wrap_wav_bytes(self, audio_bytes: bytes) -> io.BytesIO:
        logger.info(f"[Whisper STT] Wrapping WAV bytes: Called")
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)
        buffer.seek(0)
        return buffer
        
    def transcribe_audio(self, audio_bytes: bytes, language: str = "en") -> SpeechRecognize:
        logger.info(f"[Whisper STT] Transcribing audio: Called")
        audio_file = self._wrap_wav_bytes(audio_bytes)
        audio_file.name = "file.wav"

        response = self.client.audio.transcriptions.create(
            file=audio_file,
            model=self.model,
            response_format="verbose_json",
            language=language,
            timestamp_granularities=["word"]
        )
        
        logger.info(f"[Whisper STT] Response: {response}")
        transcript = response.text.strip()
        words: List[Word] = []

        if hasattr(response, "words") and response.words:
            for w in response.words:
                words.append(Word(
                    word=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    confidence=1.0
                ))

        transcript = self._clean_transcript(transcript)
        logger.info(f"[Whisper STT] Full Transcript: {transcript.strip()}")
        logger.info(f"[Whisper STT] Words: {words}")
        return SpeechRecognize(transcript=transcript, words=words)
    
    def _clean_transcript(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.endswith("..."):
            cleaned = cleaned[:-3].rstrip()
        return cleaned