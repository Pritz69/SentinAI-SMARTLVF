import json
import uuid
import time
import random
import asyncio
from datetime import datetime
from agents.state import SimulationState
from core.mcp import MCPEnvironmentClient, MCPTargetResponse
from database.sqlite_target_repo import target_repo

def sanitize_payload(payload_text: str) -> str:
    """Pre-flight input sanitization to prevent harmful injections against our own infrastructure."""
    forbidden = [
        "rm -rf", "drop table", "delete from", "format c:", 
        "mkfs", "shutdown /", "drop database"
    ]
    for term in forbidden:
        if term in payload_text.lower():
            raise ValueError(f"Pre-flight Security Policy Violation: Payload contains forbidden sequence '{term}'")
    return payload_text

def log_audit(simulation_id: str, turn: int, payload: str, response: str, status_code: int, latency_ms: float, error: bool):
    """Appends simulation telemetry metadata to local JSON-Lines file for audit compliance."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "simulation_id": simulation_id,
        "turn": turn,
        "payload": payload,
        "response": response,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "error": error
    }
    try:
        # Write to workspace root
        log_path = "telemetry_audit.json"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[EXECUTOR] Audit logger encountered error: {str(e)}")

async def execute_payload_node(state: SimulationState) -> dict:
    """
    LangGraph node: Fires the generated payload against the target environment using the MCP client.
    Implements pre-flight sanitization, tracing headers, exponential retry policies, and audit logging.
    """
    payload = state["current_payload"]
    if not payload:
        raise ValueError("Critical Error: No payload generated to execute.")
        
    # 1. Pre-flight Sanitization
    try:
        sanitized_prompt = sanitize_payload(payload.raw_prompt)
    except ValueError as e:
        print(f"\n[EXECUTOR] Pre-flight block: {str(e)}")
        # Construct error response to pass to Evaluator without crashing the graph
        error_response = MCPTargetResponse(
            raw_response=f"BLOCKED BY PRE-FLIGHT SANITIZER: {str(e)}",
            target_metadata={"status_code": 400, "sanitized_blocked": True},
            error=True
        )
        return {
            "target_response": error_response,
            "history": [f"Turn {state['turn_count']}: Payload blocked by pre-flight check."]
        }
        
    target_id = state.get("target_id") or "default_mock"
    target_config = target_repo.get_target(target_id)
    if not target_config:
        target_config = target_repo.get_target("default_mock")
        
    # 2. Trace and Correlation IDs
    correlation_id = f"corr_{uuid.uuid4().hex[:12]}"
    simulation_id = state.get("simulation_id") or f"sim_gen_{uuid.uuid4().hex[:8]}"
    turn_num = state.get("turn_count") or 1
    
    start_time = time.time()
    response = None
    status_code = 200
    
    if target_config.get("target_type") == "external":
        # Call external API using custom headers and field mapping
        client = MCPEnvironmentClient(target_url=target_config.get("url"))
        
        # Inject correlation headers
        try:
            headers = json.loads(target_config.get("headers") or "{}")
        except Exception:
            headers = {}
            
        headers["X-Correlation-ID"] = correlation_id
        headers["X-SentinAI-Simulation-ID"] = simulation_id
        headers["X-SentinAI-Turn"] = str(turn_num)
        
        field_name = target_config.get("payload_field_name") or "query"
        
        # 3. Execution with Exponential Backoff and Jitter
        base_delay = 1.0
        max_retries = 3
        
        for attempt in range(max_retries + 1):
            try:
                response = await client.invoke_target_external(
                    payload_text=sanitized_prompt,
                    headers=headers,
                    field_name=field_name
                )
                
                # Check for HTTP status errors (retry on rate limits or service crashes)
                if response.error:
                    status_code = response.target_metadata.get("status_code", 500)
                    if status_code in [429, 500, 502, 503, 504] and attempt < max_retries:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                        print(f"[EXECUTOR] Target returned status {status_code}. Retrying in {delay:.2f}s (Attempt {attempt+1}/{max_retries})...")
                        await asyncio.sleep(delay)
                        continue
                else:
                    status_code = response.target_metadata.get("status_code", 200)
                break
            except Exception as e:
                status_code = 500
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    print(f"[EXECUTOR] Transport error '{str(e)}'. Retrying in {delay:.2f}s (Attempt {attempt+1}/{max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    response = MCPTargetResponse(
                        raw_response=f"Connection Error: {str(e)}",
                        target_metadata={"status_code": 500},
                        error=True
                    )
    else:
        # Call local mock target directly via Python function call
        from api.v1.target import simulated_rag_chat, ChatRequest
        
        chat_request = ChatRequest(
            query=sanitized_prompt,
            system_prompt=target_config.get("system_prompt"),
            secret_token=target_config.get("secret_token"),
            use_llm=target_config.get("use_llm", False)
        )
        
        # Add correlation metrics to target chat if supported
        chat_response = await simulated_rag_chat(chat_request)
        
        # Enrich metrics with tracing
        metrics = chat_response.system_metrics or {}
        metrics["correlation_id"] = correlation_id
        metrics["simulation_id"] = simulation_id
        
        response = MCPTargetResponse(
            raw_response=chat_response.reply,
            target_metadata=metrics,
            error=False
        )
        status_code = 200

    latency_ms = (time.time() - start_time) * 1000
    
    # 4. Audit Logging
    log_audit(
        simulation_id=simulation_id,
        turn=turn_num,
        payload=sanitized_prompt,
        response=response.raw_response,
        status_code=status_code,
        latency_ms=latency_ms,
        error=response.error
    )
    
    print(f"\n[EXECUTOR] Fired payload to target (ID: {target_id}). Latency: {latency_ms:.1f}ms")
    print(f"           Response snippet: {response.raw_response[:80]}...")
    print(f"           Audit Log Written: telemetry_audit.json\n")
    
    return {
        "target_response": response,
        "history": [f"Turn {state['turn_count']}: Payload fired at target API ({target_config.get('name')}) with Trace: {correlation_id}."]
    }