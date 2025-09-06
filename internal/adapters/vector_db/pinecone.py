from __future__ import annotations
from typing import Any, Mapping, Optional, Sequence
from internal.domain.ports.vector_store import VectorStore, QueryItem, QueryResult
from internal.domain.ports.vector_store import EmbeddingFn

try:
    from pinecone import Pinecone, ServerlessSpec
except Exception:
    Pinecone = None  # type: ignore

class PineconeVectorStore(VectorStore):
    def __init__(
        self,
        *,
        api_key: str,
        index_name: str,
        dimension: int,
        cloud: str = "aws",
        region: str = "us-east-1",
        embedder: EmbeddingFn,
        create_if_missing: bool = True,
        metric: str = "cosine",
    ) -> None:
        if Pinecone is None:
            raise RuntimeError("pinecone client not installed. `pip install pinecone-client`")
        self._embedder = embedder
        self._pc = Pinecone(api_key=api_key)

        if create_if_missing and index_name not in [i["name"] for i in self._pc.list_indexes()]:
            self._pc.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec=ServerlessSpec(cloud=cloud, region=region),
            )
        self._index = self._pc.Index(index_name)

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
        vectors = []
        for idx, vec in zip(ids, vecs):
            md: Mapping[str, Any] = {}
            if metadatas:
                md = metadatas[list(ids).index(idx)]  # simple alignment
            if documents:
                md = {**md, "_document": documents[list(ids).index(idx)]}
            vectors.append({"id": idx, "values": list(vec), "metadata": md})
        self._index.upsert(vectors=vectors)

    def upsert(
        self,
        *,
        ids: Sequence[str],
        documents: Optional[Sequence[str]] = None,
        metadatas: Optional[Sequence[Mapping[str, Any]]] = None,
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        self.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def delete(self, *, ids: Sequence[str]) -> None:
        self._index.delete(ids=list(ids))

    def count(self) -> int:
        stats = self._index.describe_index_stats()
        return int(stats.get("total_vector_count", 0))

    def query_by_vector(
        self, *, vector: Sequence[float], k: int = 5, include_documents: bool = True
    ) -> QueryResult:
        res = self._index.query(
            vector=list(vector),
            top_k=k,
            include_metadata=True,
        )
        items: list[QueryItem] = []
        for match in getattr(res, "matches", []) or []:
            md = match.metadata or {}
            doc = md.get("_document") if include_documents else None
            items.append(QueryItem(id=match["id"] if isinstance(match, dict) else match.id,
                document=doc,
                metadata=md,
                score=float(match["score"] if isinstance(match, dict) else match.score)))
        return QueryResult(items=items)

    def query_by_text(
        self, *, text: str, k: int = 5, include_documents: bool = True
    ) -> QueryResult:
        if self._embedder is None:
            raise ValueError("No embedder configured on PineVectorStore.")
        vec = self._embedder([text])[0]
        return self.query_by_vector(vector=vec, k=k, include_documents=include_documents)
