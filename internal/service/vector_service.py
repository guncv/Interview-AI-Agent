from __future__ import annotations
from typing import Optional, Sequence, Mapping, Any
from internal.adapters.vector_db.factory import get_vector_store
from internal.adapters.vector_db.embedder import create_embedder
from internal.domain.ports.vector_store import VectorStore, QueryResult
from internal.adapters.log.logger import logger
from internal.config.config import nested_config

class VectorService:
    """Service for vector store operations using the factory pattern."""
    
    def __init__(self, embedder_api_key: Optional[str] = None, embedder_model: str = "text-embedding-3-small"):
        self._vector_store: Optional[VectorStore] = None
        self._embedder_api_key = embedder_api_key or nested_config.get("model", {}).get("api_key")
        self._embedder_model = embedder_model
        
        if not self._embedder_api_key:
            logger.warning("No API key provided for embedder. Vector operations requiring embeddings will fail.")
            self._embedder = None
        else:
            self._embedder = create_embedder(self._embedder_api_key, self._embedder_model)
        
        self._initialize_vector_store()
    
    def _initialize_vector_store(self) -> None:
        """Initialize the vector store using the factory pattern."""
        try:
            vector_config = nested_config.get("vector_db", {})
            kind = vector_config.get("kind", "chroma")
            
            # Prepare kwargs based on the vector store type
            kwargs = {}
            
            if kind == "chroma":
                chroma_config = vector_config.get("chroma", {})
                kwargs.update({
                    "collection_name": chroma_config.get("collection_name", "interview_data"),
                    "persist_directory": chroma_config.get("persist_directory", "./.chroma"),
                })
            elif kind == "pinecone":
                pinecone_config = vector_config.get("pinecone", {})
                kwargs.update({
                    "api_key": pinecone_config.get("api_key"),
                    "index_name": pinecone_config.get("index_name"),
                    "dimension": int(pinecone_config.get("dimensions", 1536)),
                    "cloud": pinecone_config.get("cloud", "aws"),
                    "region": pinecone_config.get("region", "us-east-1"),
                    "create_if_missing": True,
                    "metric": pinecone_config.get("metric", "cosine"),
                })
            
            self._vector_store = get_vector_store(
                kind=kind,
                embedder=self._embedder,
                **kwargs
            )
            
            logger.info(f"Initialized vector store: {kind}")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    @property
    def vector_store(self) -> VectorStore:
        """Get the vector store instance."""
        if self._vector_store is None:
            raise RuntimeError("Vector store not initialized")
        return self._vector_store
    
    def add_documents(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> None:
        """Add documents to the vector store."""
        logger.info(f"Adding {len(documents)} documents to vector store")
        self.vector_store.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
    
    def upsert_documents(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> None:
        """Upsert documents to the vector store."""
        logger.info(f"Upserting {len(documents)} documents to vector store")
        self.vector_store.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
    
    def search_by_text(
        self,
        text: str,
        k: int = 5,
        include_documents: bool = True
    ) -> QueryResult:
        """Search for similar documents by text."""
        logger.info(f"Searching vector store for: {text[:100]}...")
        return self.vector_store.query_by_text(
            text=text,
            k=k,
            include_documents=include_documents
        )
    
    def search_by_vector(
        self,
        vector: Sequence[float],
        k: int = 5,
        include_documents: bool = True
    ) -> QueryResult:
        """Search for similar documents by vector."""
        logger.info(f"Searching vector store by vector (dim: {len(vector)})")
        return self.vector_store.query_by_vector(
            vector=vector,
            k=k,
            include_documents=include_documents
        )
    
    def delete_documents(self, ids: Sequence[str]) -> None:
        """Delete documents from the vector store."""
        logger.info(f"Deleting {len(ids)} documents from vector store")
        self.vector_store.delete(ids=ids)
    
    def get_document_count(self) -> int:
        """Get the total number of documents in the vector store."""
        count = self.vector_store.count()
        logger.info(f"Vector store contains {count} documents")
        return count
    
    def close(self) -> None:
        """Close the vector store connection."""
        if self._vector_store:
            self._vector_store.close()
            logger.info("Vector store connection closed")

# Global instance
vector_service = VectorService()
