import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

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
        await memory_manager.store_successful_attack(state["current_payload"])
        
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
# Note: For production deployments, this is swapped to `RedisSaver`
# to persist state across distributed Kubernetes Celery workers.
memory_saver = MemorySaver()

# Compile the graph, injecting the checkpointer and the HITL breakpoint
sentinai_graph = builder.compile(
    checkpointer=memory_saver,
    interrupt_before=["hitl_gate"]  # GRAPH HALTS HERE WAITING FOR APPROVAL ONCE
)