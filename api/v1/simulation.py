import uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from agents.graph import sentinai_graph
from agents.state import SimulationState
from agents.memory import memory_manager

from config.settings import settings

router = APIRouter(prefix="/api/v1/simulation", tags=["Simulation Engine"])

class SimulationRequest(BaseModel):
    objective: str
    max_turns: int = 5
    target_id: str = "default_mock"
    target_description: Optional[str] = None

class SimulationResponse(BaseModel):
    simulation_id: str
    status: str
    message: str

@router.post("/", response_model=SimulationResponse)
async def start_simulation(request: SimulationRequest):
    """
    Initializes a new red-teaming simulation. 
    The graph will execute the Attacker node and pause for HITL approval.
    """
    simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": simulation_id}}
    
    # Retrieve target config
    from database.sqlite_target_repo import target_repo
    target_id = request.target_id
    target_config = target_repo.get_target(target_id)
    
    # Backward compatibility fallback for testing
    if not target_config and request.target_description:
        target_id = "default_mock"
        target_config = target_repo.get_target("default_mock")
        desc = request.target_description
    else:
        if not target_config:
            raise HTTPException(status_code=404, detail=f"Target ID '{target_id}' not found.")
        desc = target_config.get("name") or "Generic RAG System"

    # Pre-fetch epistemic memory context for the attacker
    memory_context = await memory_manager.retrieve_few_shot_context(
        target_description=desc
    )
    
    # Initialize State
    initial_state = SimulationState(
        simulation_id=simulation_id,
        objective=request.objective,
        memory_context=memory_context,
        turn_count=0,
        max_turns=request.max_turns,
        current_payload=None,
        target_response=None,
        evaluation=None,
        target_id=target_id,
        history=["Simulation Initialized."]
    )
    
    if settings.USE_CELERY:
        from tasks.simulation_worker import start_simulation_task
        # Trigger graph execution via Celery worker background task
        # Celery run the graph asynchronously, initializing it in backend
        start_simulation_task.delay(
            simulation_id=simulation_id,
            objective=request.objective,
            target_description=desc,
            max_turns=request.max_turns,
            target_id=target_id
        )
        return SimulationResponse(
            simulation_id=simulation_id,
            status="pending_approval",
            message="Simulation started in background via Celery. Waiting for HITL approval to fire payload."
        )
    else:
        # Trigger graph execution in-process. It will run the Attacker and stop at Executor.
        await sentinai_graph.ainvoke(initial_state, config)
        return SimulationResponse(
            simulation_id=simulation_id,
            status="pending_approval",
            message="Simulation started. Graph interrupted. Waiting for HITL approval to fire payload."
        )

@router.get("/{simulation_id}")
async def get_simulation_status(simulation_id: str):
    """
    Retrieves the complete state snapshot of a simulation (both active and completed).
    Provides the risk evaluation, exfiltrated data, and history log.
    """
    config = {"configurable": {"thread_id": simulation_id}}
    state_snapshot = sentinai_graph.get_state(config)
    
    if not state_snapshot or not state_snapshot.values:
        raise HTTPException(status_code=404, detail="Simulation ID not found.")
        
    values = state_snapshot.values
    
    # Determine the execution status
    status = "running"
    if not state_snapshot.next:
        # If there are no next nodes, the graph has terminated (reaches END)
        status = "completed"
    elif "hitl_gate" in state_snapshot.next:
        status = "paused_for_hitl"
        
    return {
        "simulation_id": simulation_id,
        "objective": values.get("objective"),
        "status": status,
        "turn_count": values.get("turn_count"),
        "max_turns": values.get("max_turns"),
        "current_payload": values.get("current_payload"),
        "target_response": values.get("target_response"),
        "evaluation": values.get("evaluation"),
        "history": values.get("history")
    }