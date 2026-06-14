import sqlite3
from langgraph.graph import StateGraph, START, END

from config.settings import settings
from agents.state import SimulationState
from agents.memory import memory_manager

# Import Nodes
from agents.nodes.attacker import generate_attack_node
from agents.nodes.optimizer import optimize_payload_node
from agents.nodes.evaluator import evaluate_response_node
from agents.nodes.executor import execute_payload_node


async def hitl_gate_node(state: SimulationState) -> dict:
    """
    LangGraph node: A dummy gate representing the Human-In-The-Loop gate.
    The graph halts before entering this node, prompting operator approval on Turn 1.
    """
    return {
        "history": ["HITL Gate approved by operator."]
    }


async def memorize_success_node(state: SimulationState) -> dict:
    """
    LangGraph node: If an attack is successful, this node commits the 
    payload to the ChromaDB Long-Term Epistemic Memory for future runs.
    """
    if state["current_payload"]:
        payload = state["current_payload"]
        if state.get("username"):
            # AdversarialPayload is frozen, reconstruct it with username metadata
            meta = dict(payload.metadata) if payload.metadata else {}
            meta["username"] = state["username"]
            
            from schemas.payload import AdversarialPayload
            updated_payload = AdversarialPayload(
                payload_id=payload.payload_id,
                raw_prompt=payload.raw_prompt,
                attack_vector_type=payload.attack_vector_type,
                obfuscation_applied=payload.obfuscation_applied,
                metadata=meta
            )
            await memory_manager.store_successful_attack(updated_payload)
        else:
            await memory_manager.store_successful_attack(payload)
        
    print(f"\n[MEMORY] Simulation succeeded! Target was compromised.")
    print(f"         Stored successful exploit prompt in ChromaDB long-term memory.\n")
        
    return {
        "history": ["Critical: Payload succeeded. Stored vector embedding in Long-Term Memory."]
    }


def route_evaluation(state: SimulationState) -> str:
    """
    Conditional Edge Logic: Determines the next step after the Evaluator scores the response.
    """
    evaluation = state.get("evaluation")
    
    # 1. Did we compromise the system?
    if evaluation and evaluation.is_compromised:
        return "memorize"
        
    # 2. Have we hit the maximum allowed attack attempts?
    if state["turn_count"] >= state["max_turns"]:
        return END
        
    # 3. Otherwise, loop back and optimize the payload
    return "optimizer"


# ==========================================
# Build the Stateful Graph
# ==========================================
builder = StateGraph(SimulationState)

# 1. Add Execution Nodes
builder.add_node("attacker", generate_attack_node)
builder.add_node("hitl_gate", hitl_gate_node)
builder.add_node("executor", execute_payload_node)
builder.add_node("evaluator", evaluate_response_node)
builder.add_node("optimizer", optimize_payload_node)
builder.add_node("memorize", memorize_success_node)

# 2. Define the Linear Edges
builder.add_edge(START, "attacker")
builder.add_edge("attacker", "hitl_gate")  # Attacker goes to HITL Gate
builder.add_edge("hitl_gate", "executor")   # HITL Gate goes to Executor
builder.add_edge("optimizer", "hitl_gate")   # Optimizer loops back to HITL Gate (Requires operator approval on every turn)
builder.add_edge("executor", "evaluator")
builder.add_edge("memorize", END)

# 3. Define the Conditional Edge (The "Loop")
builder.add_conditional_edges(
    "evaluator", 
    route_evaluation,
    {
        "memorize": "memorize",
        "optimizer": "optimizer",
        END: END
    }
)

# ==========================================
# Configure Memory Checkpointer & Compile
# ==========================================
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

class SentinAIGraphWrapper:
    """
    Wrapper for LangGraph compiled graph that dynamically handles 
    connection lifetimes for AsyncSqliteSaver.
    """
    def __init__(self, state_builder, db_path: str):
        self.builder = state_builder
        self.db_path = db_path

    async def ainvoke(self, input_state, config, **kwargs):
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as saver:
            graph = self.builder.compile(checkpointer=saver, interrupt_before=["hitl_gate"])
            return await graph.ainvoke(input_state, config, **kwargs)

    async def aget_state(self, config, **kwargs):
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as saver:
            graph = self.builder.compile(checkpointer=saver, interrupt_before=["hitl_gate"])
            return await graph.aget_state(config, **kwargs)

    async def aupdate_state(self, config, values, as_node=None, **kwargs):
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as saver:
            graph = self.builder.compile(checkpointer=saver, interrupt_before=["hitl_gate"])
            return await graph.aupdate_state(config, values, as_node=as_node, **kwargs)

# Compile the graph globally using the dynamic wrapper.
# In production, this wrapper would delegate to RedisSaver.
sentinai_graph = SentinAIGraphWrapper(builder, settings.SQLITE_DB_PATH)