import asyncio
from celery_app import celery_app
from agents.graph import sentinai_graph
from agents.state import SimulationState
from agents.memory import memory_manager

@celery_app.task(name="start_simulation_task", bind=True)
def start_simulation_task(self, simulation_id: str, objective: str, target_description: str, max_turns: int, target_id: str = "default_mock"):
    """
    Background worker task to initialize and run the first iteration of the attack graph.
    """
    async def _run_graph():
        # Retrieve context from local ChromaDB (Long-Term Memory)
        memory_context = await memory_manager.retrieve_few_shot_context(target_description)
        
        initial_state = SimulationState(
            simulation_id=simulation_id,
            objective=objective,
            memory_context=memory_context,
            turn_count=0,
            max_turns=max_turns,
            current_payload=None,
            target_response=None,
            evaluation=None,
            target_id=target_id,
            history=["Simulation Initialized via Celery Distributed Worker."]
        )
        config = {"configurable": {"thread_id": simulation_id}}
        
        # Execute the graph (it will pause at the Executor node)
        await sentinai_graph.ainvoke(initial_state, config)

    # Bridge synchronous Celery with asynchronous LangGraph
    asyncio.run(_run_graph())
    return {"simulation_id": simulation_id, "status": "paused_for_hitl"}

@celery_app.task(name="resume_simulation_task", bind=True)
def resume_simulation_task(self, simulation_id: str):
    """
    Background worker task to resume the graph after Human-In-The-Loop approval.
    """
    async def _resume_graph():
        config = {"configurable": {"thread_id": simulation_id}}
        # Passing None forces LangGraph to resume from the last saved state checkpoint
        await sentinai_graph.ainvoke(None, config)
        
    asyncio.run(_resume_graph())
    return {"simulation_id": simulation_id, "status": "graph_resumed"}