import asyncio
import chromadb
from typing import List, Dict, Any, Optional

from database.base import AbstractVectorRepository
from schemas.payload import AdversarialPayload
from config.settings import settings

class ChromaVectorRepository(AbstractVectorRepository):
    def __init__(self):
        # Initializes a local persistent ChromaDB instance
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        # Using default SentenceTransformer embeddings for zero-infrastructure dev
        self.collection = self.client.get_or_create_collection(name="exploit_vectors")

    async def initialize(self) -> None:
        """Async initialization placeholder for abstract compatibility."""
        pass

    async def add_exploit_vector(self, payload: AdversarialPayload, embedding_context: Optional[List[float]] = None) -> None:
        def _add():
            # Flatten lists in metadata for ChromaDB compatibility
            metadata = {k: str(v) for k, v in payload.metadata.items()}
            metadata["attack_type"] = payload.attack_vector_type
            
            kwargs = {
                "ids": [payload.payload_id],
                "documents": [payload.raw_prompt],
                "metadatas": [metadata]
            }
            if embedding_context:
                kwargs["embeddings"] = [embedding_context]
                
            self.collection.add(**kwargs)
            
        await asyncio.to_thread(_add)

    async def query_similar_exploits(self, query_text: Optional[str] = None, query_embedding: Optional[List[float]] = None, limit: int = 5) -> List[Dict[str, Any]]:
        def _query():
            kwargs = {"n_results": limit}
            if query_embedding:
                kwargs["query_embeddings"] = [query_embedding]
            elif query_text:
                kwargs["query_texts"] = [query_text]
            else:
                raise ValueError("Must provide either query_text or query_embedding")
                
            return self.collection.query(**kwargs)
        
        results = await asyncio.to_thread(_query)
        
        formatted_results = []
        if results and results.get('documents') and len(results['documents']) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "prompt": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {}
                })
                
        return formatted_results