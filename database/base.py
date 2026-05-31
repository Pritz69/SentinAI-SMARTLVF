from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from schemas.payload import AdversarialPayload

class AbstractVectorRepository(ABC):
    """
    Abstract interface guaranteeing seamless drop-in capability to transition 
    from local ChromaDB engine to an enterprise distributed pgvector configuration.
    """
    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def add_exploit_vector(self, payload: AdversarialPayload, embedding_context: Optional[List[float]] = None) -> None:
        pass

    @abstractmethod
    async def query_similar_exploits(self, query_text: Optional[str] = None, query_embedding: Optional[List[float]] = None, limit: int = 5) -> List[Dict[str, Any]]:
        pass

class AbstractStateRepository(ABC):
    """
    Abstract repository enforcing transactional isolation boundaries for system 
    execution states, telemetry checkpoints, and metadata records.
    """
    @abstractmethod
    async def save_execution_log(self, simulation_id: str, log_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def get_execution_log(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        pass