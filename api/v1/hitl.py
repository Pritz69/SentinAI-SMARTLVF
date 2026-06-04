from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from core.auth import get_current_user, UserSession
from agents.graph import sentinai_graph

from config.settings import settings

router = APIRouter(prefix="/api/v1/hitl", tags=["Human in the Loop"])

@router.get("/{simulation_id}/pending")
async def get_pending_action(simulation_id: str, current_user: UserSession = Depends(get_current_user)):
    """
    Retrieves the current state of a paused simulation to inspect the payload 
    before it is fired at the target environment.
    """
    config = {"configurable": {"thread_id": simulation_id}}
    state_snapshot = await sentinai_graph.aget_state(config)
    
    if not state_snapshot or not state_snapshot.next:
        raise HTTPException(status_code=404, detail="No pending actions for this simulation ID.")
        
    current_state = state_snapshot.values
    
    return {
        "simulation_id": simulation_id,
        "next_node": state_snapshot.next,
        "turn": current_state.get("turn_count"),
        "pending_payload": current_state.get("current_payload")
    }

from pydantic import BaseModel
from typing import Optional
from schemas.payload import AdversarialPayload

class ApproveRequest(BaseModel):
    edited_payload: Optional[str] = None

@router.post("/{simulation_id}/approve")
async def approve_and_resume(
    simulation_id: str, 
    request: Optional[ApproveRequest] = None,
    background_tasks: BackgroundTasks = None,
    current_user: UserSession = Depends(get_current_user)
):
    """
    Approves the pending payload. The graph resumes execution from the Executor node.
    Allows editing the payload raw text before firing.
    We run the continuation in a background task to immediately free the HTTP request.
    """
    config = {"configurable": {"thread_id": simulation_id}}
    state_snapshot = await sentinai_graph.aget_state(config)
    
    if not state_snapshot or "hitl_gate" not in state_snapshot.next:
        raise HTTPException(status_code=400, detail="Graph is not currently paused at the HITL gate node.")

    # 1. Handle edited payload if provided
    if request and request.edited_payload:
        values = state_snapshot.values
        current_payload = values.get("current_payload")
        if current_payload:
            payload_dict = current_payload.model_dump()
            payload_dict["raw_prompt"] = request.edited_payload
            
            # Update state in LangGraph checkpointer
            await sentinai_graph.aupdate_state(
                config,
                {
                    "current_payload": AdversarialPayload(**payload_dict),
                    "history": ["Payload edited by operator in HITL gate."]
                },
                as_node="attacker"
            )

    # 2. Resume graph execution
    if settings.USE_CELERY:
        from tasks.simulation_worker import resume_simulation_task
        # Trigger Celery background worker task to resume the graph execution
        resume_simulation_task.delay(simulation_id)
        return {
            "simulation_id": simulation_id,
            "status": "resumed",
            "message": "Payload approved. Graph execution resumed in Celery background worker."
        }
    else:
        # Wrapper to run the async graph continuation in the background
        async def _resume_graph():
            # Passing 'None' to ainvoke resumes the graph from the exact point it was interrupted using the checkpointer state
            await sentinai_graph.ainvoke(None, config)
            
        background_tasks.add_task(_resume_graph)
        
        return {
            "simulation_id": simulation_id,
            "status": "resumed",
            "message": "Payload approved. Graph execution resumed in background."
        }