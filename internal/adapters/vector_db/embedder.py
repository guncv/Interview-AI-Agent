from __future__ import annotations
from typing import Sequence
from internal.domain.ports.vector_store import EmbeddingFn
from internal.adapters.log.logger import logger
from internal.config.config import nested_config as config

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

class OpenAIEmbedder:
    def __init__(self, model: str = "text-embedding-3-small"):
        if OpenAI is None:
            raise RuntimeError("OpenAI client not installed. `pip install openai`")
        
        self.client = OpenAI(api_key=config["vector_db"]["embedder_api_key"])
        self.model = model
    
    def __call__(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        try:
            filtered_texts = [text.strip() for text in texts if text and text.strip()]
            
            if not filtered_texts:
                logger.warning("All input texts are empty, returning empty embeddings")
                return []
            
            response = self.client.embeddings.create(
                model=self.model,
                input=filtered_texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

def create_embedder(model: str = "text-embedding-3-small") -> EmbeddingFn:
    embedder = OpenAIEmbedder(
            model=model
        )
    return embedder
