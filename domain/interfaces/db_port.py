from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class DatabasePort(ABC):
    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError
    
    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        raise NotImplementedError
    
    @abstractmethod
    def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        raise NotImplementedError

