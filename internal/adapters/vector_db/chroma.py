from __future__ import annotations
from typing import Any, Mapping, Optional, Sequence
from internal.domain.ports.vector_store import VectorStore, EmbeddingFn, QueryItem, QueryResult

try:
    import chromadb
    from chromadb.config import Settings
except Exception as e:
    chromadb = None
    Settings = None

class ChromaVectorStore(VectorStore):
    def __init__(
        self,
        *,
        collection_name: str = "interview_data",
        persist_directory: str = "./.chroma",
        embedder: Optional[EmbeddingFn] = None,
    ) -> None:
        if chromadb is None:
            raise RuntimeError("chromadb is not installed. `pip install chromadb`")
        self._embedder = embedder
        self._client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(name=collection_name)

    def _ensure_embeddings(
        self,
        *,
        documents: Optional[Sequence[str]],
        embeddings: Optional[Sequence[Sequence[float]]],
    ) -> Sequence[Sequence[float]]:
        if embeddings is not None:
            return embeddings
        if documents is None or self._embedder is None:
            raise ValueError("Embeddings not provided and no embedder configured.")
        return self._embedder(documents)

    def add(
        self,
        *,
        ids: Sequence[str],
        documents: Optional[Sequence[str]] = None,
        metadatas: Optional[Sequence[Mapping[str, Any]]] = None,
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        vecs = self._ensure_embeddings(documents=documents, embeddings=embeddings)
        self._col.add(ids=list(ids), documents=documents, metadatas=metadatas, embeddings=vecs)

    def upsert(
        self,
        *,
        ids: Sequence[str],
        documents: Optional[Sequence[str]] = None,
        metadatas: Optional[Sequence[Mapping[str, Any]]] = None,
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        self.delete(ids=ids)
        self.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    def delete(self, *, ids: Sequence[str]) -> None:
        self._col.delete(ids=list(ids))

    def count(self) -> int:
        return self._col.count()

    def query_by_vector(
        self, *, vector: Sequence[float], k: int = 5, include_documents: bool = True
    ) -> QueryResult:
        res = self._col.query(
            query_embeddings=[list(vector)],
            n_results=k,
            include=["documents" if include_documents else None, "metadatas", "distances"],
        )
        docs = res.get("documents", [[]])[0] if include_documents else [None] * len(res["ids"][0])
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        ids = res["ids"][0]

        items = [
            QueryItem(id=i, document=d, metadata=m or {}, score=(1 - dist if dist is not None else None))
            for i, d, m, dist in zip(ids, docs, metas, dists)
        ]
        return QueryResult(items=items)

    def query_by_text(
        self, *, text: str, k: int = 5, include_documents: bool = True
    ) -> QueryResult:
        if self._embedder is None:
            raise ValueError("No embedder configured on ChromVectorStore.")
        vec = self._embedder([text])[0]
        return self.query_by_vector(vector=vec, k=k, include_documents=include_documents)
