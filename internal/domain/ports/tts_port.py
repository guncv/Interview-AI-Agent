from abc import ABC, abstractmethod
from typing import AsyncGenerator

class TTSPort(ABC):
    @abstractmethod
    async def synthesize_stream(self, text: str, session_id: str) -> AsyncGenerator[bytes, None]:
        pass
