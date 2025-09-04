from abc import ABC, abstractmethod

class STTPort(ABC):
    @abstractmethod
    async def transcribe(self, audio_chunk: bytes, session_id: str) -> str:
        return ""
