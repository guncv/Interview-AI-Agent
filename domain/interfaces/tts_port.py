from abc import ABC, abstractmethod
from typing import AsyncGenerator

class TTSPort(ABC):
    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        pass

