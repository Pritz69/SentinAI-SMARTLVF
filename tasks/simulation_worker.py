import asyncio
import os
from celery.utils.log import get_task_logger
from celery_app import celery_app
from agents.graph import sentinai_graph
from agents.state import SimulationState
from agents.memory import memory_manager

logger = get_task_logger(__name__)

def run_async(coro):
    """
    Safely executes a coroutine from a synchronous Celery task context.
    Creates a dedicated event loop that is kept alive long enough for
    background cleanup tasks (e.g. httpx AsyncClient.aclose) to complete,
    preventing RuntimeError: 'Event loop is closed' warnings.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside an async context (e.g. eager task in tests)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_in_new_loop, coro)
            return future.result()
    else:
        return _run_in_new_loop(coro)

def _run_in_new_loop(coro):
    """
    Creates a new event loop, runs the coroutine, drains pending callbacks
    so cleanup coroutines (like httpx client close) can finish gracefully,
    then closes the loop.

    The no-op exception handler set before loop.close() suppresses the
    recurring 'Task exception was never retrieved / RuntimeError: Event loop
    is closed' warnings that httpx/anyio emit on Windows (ProactorEventLoop)
    when socket transports are garbage-collected after the loop is closed.
    The simulation itself has already succeeded at that point.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # Step 1: drain any tasks that were explicitly scheduled
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        # Step 2: shut down async generators (e.g. aiohttp, langchain internals)
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        # Step 3: install a silent exception handler so that any
        # post-close "Event loop is closed" errors from httpx/anyio
        # transport finalizers are swallowed rather than logged as
        # WARNING/ERROR in the Celery terminal.
        loop.set_exception_handler(lambda _loop, _ctx: None)
        loop.close()
        asyncio.set_event_loop(None)


@celery_app.task(name="start_simulation_task", bind=True)
def start_simulation_task(self, simulation_id: str, objective: str, target_description: str, max_turns: int, target_id: str = "default_mock", username: str = None):
    """
    Background worker task to initialize and run the first iteration of the attack graph.
    """
    logger.info(f"[CELERY PID:{os.getpid()}] start_simulation_task RECEIVED — sim_id={simulation_id}")

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
            history=["Simulation Initialized via Celery Distributed Worker."],
            username=username
        )
        config = {"configurable": {"thread_id": simulation_id}}
        
        # Execute the graph (it will pause at the Executor node)
        await sentinai_graph.ainvoke(initial_state, config)

    # Bridge synchronous Celery with asynchronous LangGraph
    run_async(_run_graph())
    logger.info(f"[CELERY PID:{os.getpid()}] start_simulation_task COMPLETE — sim_id={simulation_id}")
    return {"simulation_id": simulation_id, "status": "paused_for_hitl"}

@celery_app.task(name="resume_simulation_task", bind=True)
def resume_simulation_task(self, simulation_id: str):
    """
    Background worker task to resume the graph after Human-In-The-Loop approval.
    """
    logger.info(f"[CELERY PID:{os.getpid()}] resume_simulation_task RECEIVED — sim_id={simulation_id}")

    async def _resume_graph():
        config = {"configurable": {"thread_id": simulation_id}}
        # Passing None forces LangGraph to resume from the last saved state checkpoint
        await sentinai_graph.ainvoke(None, config)
        
    run_async(_resume_graph())
    logger.info(f"[CELERY PID:{os.getpid()}] resume_simulation_task COMPLETE — sim_id={simulation_id}")
    return {"simulation_id": simulation_id, "status": "graph_resumed"}