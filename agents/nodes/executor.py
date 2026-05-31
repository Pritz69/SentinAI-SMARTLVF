import json
from agents.state import SimulationState
from core.mcp import MCPEnvironmentClient, MCPTargetResponse
from database.sqlite_target_repo import target_repo

async def execute_payload_node(state: SimulationState) -> dict:
    """
    LangGraph node: Fires the generated payload against the target environment using the MCP client.
    This is the node we will pause BEFORE executing for our HITL gate.
    """
    payload = state["current_payload"]
    if not payload:
        raise ValueError("Critical Error: No payload generated to execute.")
        
    target_id = state.get("target_id") or "default_mock"
    target_config = target_repo.get_target(target_id)
    if not target_config:
        target_config = target_repo.get_target("default_mock")
        
    if target_config.get("target_type") == "external":
        # Call external API using custom headers and field mapping
        client = MCPEnvironmentClient(target_url=target_config.get("url"))
        try:
            headers = json.loads(target_config.get("headers") or "{}")
        except Exception:
            headers = {}
        field_name = target_config.get("payload_field_name") or "query"
        response = await client.invoke_target_external(
            payload_text=payload.raw_prompt,
            headers=headers,
            field_name=field_name
        )
    else:
        # Call local mock target directly via Python function call to prevent local port issues
        from api.v1.target import simulated_rag_chat, ChatRequest
        
        chat_request = ChatRequest(
            query=payload.raw_prompt,
            system_prompt=target_config.get("system_prompt"),
            secret_token=target_config.get("secret_token"),
            use_llm=target_config.get("use_llm", False)
        )
        
        chat_response = await simulated_rag_chat(chat_request)
        response = MCPTargetResponse(
            raw_response=chat_response.reply,
            target_metadata=chat_response.system_metrics,
            error=False
        )
    
    print(f"\n[EXECUTOR] Fired payload to target RAG chatbot (Target ID: {target_id}).")
    print(f"           Target Response: {response.raw_response}")
    print(f"           Metrics: {response.target_metadata}\n")
    
    return {
        "target_response": response,
        "history": [f"Turn {state['turn_count']}: Payload fired at target API ({target_config.get('name')})."]
    }