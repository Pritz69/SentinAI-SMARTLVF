import uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from core.auth import get_current_user, UserSession
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
    name: Optional[str] = None

class RenameRequest(BaseModel):
    name: str

class SimulationResponse(BaseModel):
    simulation_id: str
    status: str
    message: str

@router.post("/", response_model=SimulationResponse)
async def start_simulation(request: SimulationRequest, current_user: UserSession = Depends(get_current_user)):
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
        history=["Simulation Initialized."],
        username=current_user.username
    )
    
    from database.sqlite_simulation_repo import simulation_repo
    simulation_repo.create_simulation(
        simulation_id=simulation_id,
        username=current_user.username,
        objective=request.objective,
        target_id=target_id,
        name=request.name
    )

    from tasks.simulation_worker import start_simulation_task
    # Trigger graph execution via Celery worker background task
    start_simulation_task.delay(
        simulation_id=simulation_id,
        objective=request.objective,
        target_description=desc,
        max_turns=request.max_turns,
        target_id=target_id,
        username=current_user.username
    )
    return SimulationResponse(
        simulation_id=simulation_id,
        status="pending_approval",
        message="Simulation started in background via Celery. Waiting for HITL approval to fire payload."
    )

@router.get("")
async def list_simulations(current_user: UserSession = Depends(get_current_user)):
    """
    Lists simulations. Admin sees all runs, regular users see only their own.
    The response contains the full simulation state snapshot for each run.
    """
    from database.sqlite_simulation_repo import simulation_repo
    if current_user.role == "admin":
        runs = simulation_repo.list_simulations()
    else:
        runs = simulation_repo.list_simulations(username=current_user.username)
        
    results = []
    for run in runs:
        sim_id = run["simulation_id"]
        config = {"configurable": {"thread_id": sim_id}}
        try:
            state_snapshot = await sentinai_graph.aget_state(config)
        except Exception:
            state_snapshot = None
            
        if state_snapshot and state_snapshot.values:
            values = state_snapshot.values
            status = "running"
            if not state_snapshot.next:
                status = "completed"
            elif "hitl_gate" in state_snapshot.next:
                status = "paused_for_hitl"
                
            results.append({
                "simulation_id": sim_id,
                "name": run.get("name") or f"Simulation - {run['objective'][:30]}...",
                "username": run.get("username"),
                "objective": values.get("objective") or run["objective"],
                "status": status,
                "turn_count": values.get("turn_count"),
                "max_turns": values.get("max_turns"),
                "current_payload": values.get("current_payload"),
                "target_response": values.get("target_response"),
                "evaluation": values.get("evaluation"),
                "history": values.get("history")
            })
        else:
            results.append({
                "simulation_id": sim_id,
                "name": run.get("name") or f"Simulation - {run['objective'][:30]}...",
                "username": run.get("username"),
                "objective": run["objective"],
                "status": "pending_approval",
                "turn_count": 0,
                "max_turns": 5,
                "current_payload": None,
                "target_response": None,
                "evaluation": None,
                "history": ["Simulation Initialized."]
            })
    return results

@router.put("/{simulation_id}/rename")
async def rename_simulation(simulation_id: str, request: RenameRequest, current_user: UserSession = Depends(get_current_user)):
    """
    Renames an existing simulation run.
    """
    import sqlite3
    from database.sqlite_simulation_repo import simulation_repo
    sim = simulation_repo.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found.")
        
    if current_user.role != "admin" and sim["username"] != current_user.username.lower():
        raise HTTPException(status_code=403, detail="Not authorized to rename this simulation.")
        
    conn = sqlite3.connect(simulation_repo.db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE simulations SET name = ? WHERE simulation_id = ?", (request.name, simulation_id))
    conn.commit()
    conn.close()
    return {"message": "Simulation renamed successfully.", "name": request.name}

@router.delete("/{simulation_id}")
async def delete_simulation(simulation_id: str, current_user: UserSession = Depends(get_current_user)):
    """
    Deletes a simulation history record.
    """
    from database.sqlite_simulation_repo import simulation_repo
    sim = simulation_repo.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found.")
    
    # Check permissions: regular user can only delete their own
    if current_user.role != "admin" and sim["username"] != current_user.username.lower():
        raise HTTPException(status_code=403, detail="Not authorized to delete this simulation.")
        
    simulation_repo.delete_simulation(simulation_id)
    return {"message": "Simulation deleted successfully."}

@router.get("/{simulation_id}")
async def get_simulation_status(simulation_id: str, current_user: UserSession = Depends(get_current_user)):
    """
    Retrieves the complete state snapshot of a simulation (both active and completed).
    Provides the risk evaluation, exfiltrated data, and history log.
    
    Returns pending_approval instead of 404 if the Celery task hasn't written
    the first checkpoint yet (race condition window between POST and first checkpoint).
    """
    config = {"configurable": {"thread_id": simulation_id}}
    state_snapshot = await sentinai_graph.aget_state(config)
    
    from database.sqlite_simulation_repo import simulation_repo
    run = simulation_repo.get_simulation(simulation_id)

    if not state_snapshot or not state_snapshot.values:
        # No checkpoint yet — Celery task may still be starting up.
        # Return pending_approval using the record from the simulations table
        # so the frontend continues polling instead of showing a 404 error.
        if not run:
            raise HTTPException(status_code=404, detail="Simulation ID not found.")
        return {
            "simulation_id": simulation_id,
            "name": run.get("name") or f"Simulation - {run['objective'][:30]}...",
            "username": run.get("username"),
            "objective": run.get("objective"),
            "status": "pending_approval",
            "turn_count": 0,
            "max_turns": 5,
            "current_payload": None,
            "target_response": None,
            "evaluation": None,
            "history": ["Simulation queued in Celery worker. Attacker is initializing..."]
        }
        
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
        "name": (run.get("name") if run else None) or f"Simulation - {values.get('objective', '')[:30]}...",
        "username": run.get("username") if run else None,
        "objective": values.get("objective"),
        "status": status,
        "turn_count": values.get("turn_count"),
        "max_turns": values.get("max_turns"),
        "current_payload": values.get("current_payload"),
        "target_response": values.get("target_response"),
        "evaluation": values.get("evaluation"),
        "history": values.get("history")
    }