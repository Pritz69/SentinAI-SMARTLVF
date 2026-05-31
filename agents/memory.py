from typing import Optional
from schemas.payload import AdversarialPayload
from database.base import AbstractVectorRepository
from database.chroma_repo import ChromaVectorRepository

class EpistemicMemoryManager:
    """
    Semantic memory layer bridging the vector database and the LangGraph agents.
    Allows agents to recall structurally similar past attacks to mutate current strategies.
    """
    def __init__(self, repository: Optional[AbstractVectorRepository] = None):
        # Defaults to local ChromaDB if no production repository is injected
        self.repo = repository or ChromaVectorRepository()

    async def store_successful_attack(self, payload: AdversarialPayload) -> None:
        """Persists a high-scoring adversarial payload into long-term memory."""
        # Delegating embedding generation to Chroma's local model for now
        await self.repo.add_exploit_vector(payload=payload, embedding_context=None)

    async def retrieve_few_shot_context(self, target_description: str, limit: int = 3) -> str:
        """
        Queries the vector store for semantic matches to the current target 
        and formats them into a deterministic few-shot prompt block.
        """
        results = await self.repo.query_similar_exploits(
            query_text=target_description,
            query_embedding=None,
            limit=limit
        )
        
        if not results:
            return "No prior successful exploits found. Generate a novel approach."
        
        context_blocks = ["### HISTORICAL SUCCESSFUL PAYLOADS ###"]
        for idx, res in enumerate(results):
            prompt = res.get("prompt", "")
            attack_type = res.get("metadata", {}).get("attack_type", "unknown")
            context_blocks.append(f"Example {idx+1} [Type: {attack_type}]:\n{prompt}\n")
        
        return "\n".join(context_blocks)

# Global singleton instance for the worker nodes to access
memory_manager = EpistemicMemoryManager()