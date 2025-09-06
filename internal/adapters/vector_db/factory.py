from __future__ import annotations
import os
from typing import Any, Mapping, Optional
from internal.domain.ports.vector_store import VectorStore, EmbeddingFn
from internal.adapters.vector_db.chroma import ChromaVectorStore
from internal.config.config import nested_config as config

def get_vector_store(
    *,
    collection_name: str,
    embedder: Optional[EmbeddingFn] = None,
    **kwargs: Any,
) -> VectorStore:

    kind = (config["vector_db"]["kind"] or "chroma").lower()

    if kind == "chroma":
        return ChromaVectorStore(
            collection_name=collection_name,
            persist_directory=kwargs.get("persist_directory", "./.chroma"),
            embedder=embedder,
        )

    if kind == "pinecone":
        from internal.adapters.vector_db.pinecone import PineconeVectorStore
        required = ["api_key", "index_name", "dimension"]
        missing = [k for k in required if k not in kwargs]
        if missing:
            raise ValueError(f"Missing required Pinecone kwargs: {missing}")
        return PineconeVectorStore(
            api_key=kwargs["api_key"],
            index_name=kwargs["index_name"],
            dimension=int(kwargs["dimension"]),
            cloud=kwargs.get("cloud", "aws"),
            region=kwargs.get("region", "us-east-1"),
            embedder=embedder,
            create_if_missing=kwargs.get("create_if_missing", True),
            metric=kwargs.get("metric", "cosine"),
        )

    raise ValueError(f"Unknown vector store kind: {kind}")
