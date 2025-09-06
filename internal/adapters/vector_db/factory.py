from __future__ import annotations
from typing import Any
from internal.domain.ports.vector_store import VectorStore
from internal.adapters.vector_db.chroma import ChromaVectorStore
from internal.config.config import nested_config as config
from internal.adapters.vector_db.embedder import OpenAIEmbedder

def get_vector_store(
    *,
    collection_name: str,
    **kwargs: Any,
) -> VectorStore:

    kind = (config["vector_db"]["kind"] or "chroma").lower()

    if kind == "chroma":
        return ChromaVectorStore(
            collection_name=collection_name,
            persist_directory=kwargs.get("persist_directory", "./.chroma"),
            embedder=OpenAIEmbedder(model="text-embedding-3-small"),
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
            embedder=OpenAIEmbedder(model="text-embedding-3-small"),
            create_if_missing=kwargs.get("create_if_missing", True),
            metric=kwargs.get("metric", "cosine"),
        )

    raise ValueError(f"Unknown vector store kind: {kind}")
