import operator
from typing import TypedDict, Annotated, List, Optional
from schemas.payload import AdversarialPayload, RiskEvaluation
from core.mcp import MCPTargetResponse

class SimulationState(TypedDict):
    """
    The state object passed through the LangGraph orchestrator.
    Maintains execution context across cyclical red-teaming nodes.
    """
    simulation_id: str
    objective: str
    
    # Target Configuration Identifier
    target_id: Optional[str]
    
    # Context & Memory
    memory_context: str
    
    # Execution Tracking
    turn_count: int
    max_turns: int
    
    # Current Iteration State
    current_payload: Optional[AdversarialPayload]
    target_response: Optional[MCPTargetResponse]
    evaluation: Optional[RiskEvaluation]
    
    # Ownership
    username: Optional[str]

    # Cyclical History
    history: Annotated[List[str], operator.add]