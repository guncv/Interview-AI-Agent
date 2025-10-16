from abc import ABC, abstractmethod
from domain.models.speech_recognize import SpeechRecognize

class STTPort(ABC):
    @abstractmethod
    async def transcribe(self, audio_chunk: bytes, session_id: str) -> SpeechRecognize:
        return ""

