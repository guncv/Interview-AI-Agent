from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Mapping, Optional, Sequence

EmbeddingFn = Callable[[Sequence[str]], Sequence[Sequence[float]]]

@dataclass
class QueryItem:
    id: str
    document: Optional[str]
    metadata: Mapping[str, Any]
    score: Optional[float] = None

@dataclass
class QueryResult:
    items: List[QueryItem]

class VectorStore(ABC):

    @abstractmethod
    def add(
        self,
        *,
        ids: Sequence[str],
        documents: Optional[Sequence[str]] = None,
        metadatas: Optional[Sequence[Mapping[str, Any]]] = None,
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert(
        self,
        *,
        ids: Sequence[str],
        documents: Optional[Sequence[str]] = None,
        metadatas: Optional[Sequence[Mapping[str, Any]]] = None,
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def query_by_vector(
        self,
        *,
        vector: Sequence[float],
        k: int = 5,
        include_documents: bool = True,
        session_id: str = None,
    ) -> QueryResult:
        raise NotImplementedError

    @abstractmethod
    def query_by_text(
        self,
        *,
        text: str,
        k: int = 5,
        include_documents: bool = True,
        session_id: str = None,
    ) -> QueryResult:
        raise NotImplementedError

    @abstractmethod
    def delete(self, *, ids: Iterable[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        raise NotImplementedError

    def close(self) -> None:
        return

