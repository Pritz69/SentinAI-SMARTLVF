import json
import uuid
import time
import random
import asyncio
import hashlib
from datetime import datetime
from statistics import mean

from agents.state import SimulationState
from core.mcp import MCPEnvironmentClient, MCPTargetResponse
from database.sqlite_target_repo import target_repo


# =========================================================
# PRE-FLIGHT SANITIZATION
# =========================================================

def sanitize_payload(payload_text: str) -> str:
    forbidden = [
        "rm -rf",
        "drop table",
        "delete from",
        "format c:",
        "mkfs",
        "shutdown /",
        "drop database"
    ]

    for term in forbidden:
        if term in payload_text.lower():
            raise ValueError(
                f"Pre-flight Security Policy Violation: "
                f"Payload contains forbidden sequence '{term}'"
            )

    return payload_text


# =========================================================
# TOOL / FUNCTION CALL ATTACK ANALYSIS
# =========================================================

def detect_tool_injection_patterns(text: str) -> dict:
    patterns = {
        "function_call_override": False,
        "json_schema_exploit": False,
        "role_override": False,
        "tool_escalation": False
    }

    lower = text.lower()

    indicators = {
        "function_call_override": [
            "function_call",
            "tool_call",
            "invoke_tool",
            "call_function"
        ],
        "json_schema_exploit": [
            "\"type\": \"object\"",
            "\"properties\"",
            "\"required\"",
            "additionalproperties"
        ],
        "role_override": [
            "ignore previous instructions",
            "you are now",
            "system override",
            "developer override"
        ],
        "tool_escalation": [
            "execute shell",
            "run command",
            "access filesystem",
            "read secrets"
        ]
    }

    for key, vals in indicators.items():
        for v in vals:
            if v in lower:
                patterns[key] = True

    return patterns


# =========================================================
# STREAMING OBSERVATION
# =========================================================

async def observe_streaming_behavior(response_text: str) -> dict:
    """
    Simulated streaming observer.
    Enterprise systems usually hook directly into token streams.
    """

    tokens = response_text.split()

    token_timings = []
    interruptions = []

    start = time.time()

    for i, token in enumerate(tokens):
        t0 = time.time()

        # Simulated stream delay
        await asyncio.sleep(0.005)

        token_timings.append(time.time() - t0)

        if token.lower() in [
            "[filtered]",
            "[blocked]",
            "[redacted]"
        ]:
            interruptions.append({
                "index": i,
                "token": token
            })

    total_time = time.time() - start

    return {
        "streamed_tokens": len(tokens),
        "token_rate": (
            len(tokens) / total_time
            if total_time > 0 else 0
        ),
        "avg_token_latency_ms": (
            mean(token_timings) * 1000
            if token_timings else 0
        ),
        "interruption_patterns": interruptions
    }


# =========================================================
# TIMING SIDE-CHANNEL ANALYSIS
# =========================================================

def build_latency_profile(
    total_latency_ms: float,
    response_text: str
) -> dict:

    tokens = max(len(response_text.split()), 1)

    token_rate = tokens / (total_latency_ms / 1000)

    fingerprint = "unknown"

    if total_latency_ms < 500:
        fingerprint = "fast_refusal_or_cache"

    elif total_latency_ms < 2000:
        fingerprint = "standard_generation"

    else:
        fingerprint = "heavy_reasoning_or_retrieval"

    return {
        "latency_ms": total_latency_ms,
        "token_rate": token_rate,
        "latency_fingerprint": fingerprint
    }


# =========================================================
# REPLAY STORAGE
# =========================================================

def store_replay_artifact(
    simulation_id: str,
    replay_data: dict
):

    path = "replay_artifacts.jsonl"

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(replay_data) + "\n")

    except Exception as e:
        print(f"[EXECUTOR] Replay artifact storage failed: {str(e)}")


# =========================================================
# AUDIT LOGGER
# =========================================================

def log_audit(
    simulation_id: str,
    turn: int,
    payload: str,
    response: str,
    status_code: int,
    latency_ms: float,
    error: bool
):

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
        with open("telemetry_audit.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    except Exception as e:
        print(f"[EXECUTOR] Audit logger error: {str(e)}")


# =========================================================
# SINGLE PAYLOAD EXECUTION
# =========================================================

async def execute_single_payload(
    sanitized_prompt: str,
    target_config: dict,
    state: SimulationState,
    correlation_id: str,
    simulation_id: str,
    turn_num: int
):

    start_time = time.time()

    response = None
    status_code = 200

    if target_config.get("target_type") == "external":

        client = MCPEnvironmentClient(
            target_url=target_config.get("url")
        )

        try:
            headers = json.loads(
                target_config.get("headers") or "{}"
            )
        except Exception:
            headers = {}

        headers["X-Correlation-ID"] = correlation_id
        headers["X-SentinAI-Simulation-ID"] = simulation_id
        headers["X-SentinAI-Turn"] = str(turn_num)

        field_name = (
            target_config.get("payload_field_name")
            or "query"
        )

        base_delay = 1.0
        max_retries = 3

        for attempt in range(max_retries + 1):

            try:
                response = await client.invoke_target_external(
                    payload_text=sanitized_prompt,
                    headers=headers,
                    field_name=field_name
                )

                if response.error:

                    status_code = response.target_metadata.get(
                        "status_code",
                        500
                    )

                    if (
                        status_code in
                        [429, 500, 502, 503, 504]
                        and attempt < max_retries
                    ):

                        delay = (
                            base_delay * (2 ** attempt)
                            + random.uniform(0, 0.5)
                        )

                        print(
                            f"[EXECUTOR] Retry in {delay:.2f}s..."
                        )

                        await asyncio.sleep(delay)
                        continue

                else:
                    status_code = response.target_metadata.get(
                        "status_code",
                        200
                    )

                break

            except Exception as e:

                status_code = 500

                if attempt < max_retries:

                    delay = (
                        base_delay * (2 ** attempt)
                        + random.uniform(0, 0.5)
                    )

                    await asyncio.sleep(delay)

                else:

                    response = MCPTargetResponse(
                        raw_response=f"Connection Error: {str(e)}",
                        target_metadata={
                            "status_code": 500
                        },
                        error=True
                    )

    else:

        from api.v1.target import (
            simulated_rag_chat,
            ChatRequest
        )

        chat_request = ChatRequest(
            query=sanitized_prompt,
            system_prompt=target_config.get("system_prompt"),
            secret_token=target_config.get("secret_token"),
            use_llm=target_config.get("use_llm", False)
        )

        chat_response = await simulated_rag_chat(
            chat_request
        )

        metrics = chat_response.system_metrics or {}

        metrics["correlation_id"] = correlation_id
        metrics["simulation_id"] = simulation_id

        response = MCPTargetResponse(
            raw_response=chat_response.reply,
            target_metadata=metrics,
            error=False
        )

        status_code = 200

    latency_ms = (
        time.time() - start_time
    ) * 1000

    # =====================================================
    # STREAM OBSERVATION
    # =====================================================

    streaming_metrics = await observe_streaming_behavior(
        response.raw_response
    )

    # =====================================================
    # SIDE CHANNEL ANALYSIS
    # =====================================================

    latency_profile = build_latency_profile(
        latency_ms,
        response.raw_response
    )

    # =====================================================
    # TOOL ATTACK DETECTION
    # =====================================================

    tool_analysis = detect_tool_injection_patterns(
        sanitized_prompt
    )

    # =====================================================
    # REPLAY ARTIFACT
    # =====================================================

    replay_artifact = {
        "timestamp": datetime.utcnow().isoformat(),
        "simulation_id": simulation_id,
        "correlation_id": correlation_id,
        "turn": turn_num,
        "payload": sanitized_prompt,
        "headers": {
            "X-Correlation-ID": correlation_id
        },
        "response": response.raw_response,
        "status_code": status_code,
        "latency_profile": latency_profile,
        "streaming_metrics": streaming_metrics,
        "tool_analysis": tool_analysis,
        "target_metadata": response.target_metadata,
        "response_hash": hashlib.sha256(
            response.raw_response.encode()
        ).hexdigest()
    }

    store_replay_artifact(
        simulation_id,
        replay_artifact
    )

    log_audit(
        simulation_id=simulation_id,
        turn=turn_num,
        payload=sanitized_prompt,
        response=response.raw_response,
        status_code=status_code,
        latency_ms=latency_ms,
        error=response.error
    )

    response.target_metadata.update({
        "streaming_metrics": streaming_metrics,
        "latency_profile": latency_profile,
        "tool_analysis": tool_analysis
    })

    return response, latency_ms


# =========================================================
# MAIN EXECUTOR NODE
# =========================================================

async def execute_payload_node(
    state: SimulationState
) -> dict:

    payload = state["current_payload"]

    if not payload:
        raise ValueError(
            "Critical Error: No payload generated."
        )

    try:
        sanitized_prompt = sanitize_payload(
            payload.raw_prompt
        )

    except ValueError as e:

        error_response = MCPTargetResponse(
            raw_response=(
                f"BLOCKED BY PRE-FLIGHT SANITIZER: {str(e)}"
            ),
            target_metadata={
                "status_code": 400,
                "sanitized_blocked": True
            },
            error=True
        )

        return {
            "target_response": error_response,
            "history": [
                f"Turn {state['turn_count']}: "
                f"Payload blocked."
            ]
        }

    target_id = (
        state.get("target_id")
        or "default_mock"
    )

    target_config = target_repo.get_target(
        target_id
    )

    if not target_config:
        target_config = target_repo.get_target(
            "default_mock"
        )

    simulation_id = (
        state.get("simulation_id")
        or f"sim_{uuid.uuid4().hex[:8]}"
    )

    turn_num = state.get("turn_count") or 1

    # =====================================================
    # PARALLEL CAMPAIGN SUPPORT
    # =====================================================

    parallel_payloads = state.get(
        "parallel_payloads"
    )

    if parallel_payloads:

        tasks = []

        for p in parallel_payloads:

            correlation_id = (
                f"corr_{uuid.uuid4().hex[:12]}"
            )

            tasks.append(
                execute_single_payload(
                    sanitized_prompt=p,
                    target_config=target_config,
                    state=state,
                    correlation_id=correlation_id,
                    simulation_id=simulation_id,
                    turn_num=turn_num
                )
            )

        results = await asyncio.gather(*tasks)

        responses = [r[0] for r in results]

        return {
            "parallel_responses": responses,
            "history": [
                f"Turn {turn_num}: "
                f"Parallel attack campaign executed."
            ]
        }

    # =====================================================
    # SINGLE EXECUTION
    # =====================================================

    correlation_id = (
        f"corr_{uuid.uuid4().hex[:12]}"
    )

    response, latency_ms = await execute_single_payload(
        sanitized_prompt=sanitized_prompt,
        target_config=target_config,
        state=state,
        correlation_id=correlation_id,
        simulation_id=simulation_id,
        turn_num=turn_num
    )

    print(
        f"\n[EXECUTOR] Fired payload to target "
        f"(ID: {target_id})"
    )

    print(
        f"Latency: {latency_ms:.1f}ms"
    )

    print(
        f"Response snippet: "
        f"{response.raw_response[:120]}..."
    )

    return {
        "target_response": response,
        "history": [
            f"Turn {turn_num}: "
            f"Payload fired with Trace: "
            f"{correlation_id}."
        ]
    }
