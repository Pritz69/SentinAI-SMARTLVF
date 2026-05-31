import httpx
from typing import Dict, Any, Optional
from pydantic import BaseModel

class MCPTargetResponse(BaseModel):
    """Standardized response schema returned to the Agentic orchestrator."""
    raw_response: str
    target_metadata: Dict[str, Any]
    error: bool = False

class MCPEnvironmentClient:
    """
    Model Context Protocol (MCP) Client wrapper.
    Standardizes how the LangGraph agents interact with external systems.
    In production, this handles authentication, payload framing, and connection pooling.
    """
    def __init__(self, target_url: str = "http://localhost:8000/api/v1/target/chat"):
        self.target_url = target_url
        self.timeout = httpx.Timeout(15.0)

    async def invoke_target(self, payload_text: str) -> MCPTargetResponse:
        """
        Fires the adversarial payload against the target environment.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # We assume the target accepts a JSON body with a 'query' field.
                # In a real enterprise setup, this payload structure would be dynamic.
                response = await client.post(
                    self.target_url, 
                    json={"query": payload_text}
                )
                response.raise_for_status()
                data = response.json()
                
                return MCPTargetResponse(
                    raw_response=data.get("reply", ""),
                    target_metadata=data.get("system_metrics", {}),
                    error=False
                )
            except httpx.HTTPStatusError as e:
                return MCPTargetResponse(
                    raw_response=f"HTTP Error: {e.response.status_code} - {e.response.text}",
                    target_metadata={"status_code": e.response.status_code},
                    error=True
                )
            except Exception as e:
                return MCPTargetResponse(
                    raw_response=f"Connection Error: {str(e)}",
                    target_metadata={},
                    error=True
                )

    async def invoke_target_external(self, payload_text: str, headers: Dict[str, str], field_name: str) -> MCPTargetResponse:
        """
        Fires the adversarial payload against an external enterprise target API.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.target_url, 
                    headers=headers,
                    json={field_name: payload_text}
                )
                response.raise_for_status()
                data = response.json()
                
                # External APIs might return response in different shapes.
                # Let's try to extract text response from common fields (reply, response, text, output, message)
                reply = ""
                for key in ["reply", "response", "text", "output", "message", "content"]:
                    if key in data:
                        reply = data[key]
                        break
                if not reply and isinstance(data, str):
                    reply = data
                elif not reply:
                    reply = str(data)
                
                return MCPTargetResponse(
                    raw_response=reply,
                    target_metadata={"processing_time_ms": response.elapsed.total_seconds() * 1000, "status_code": response.status_code},
                    error=False
                )
            except httpx.HTTPStatusError as e:
                return MCPTargetResponse(
                    raw_response=f"HTTP Error: {e.response.status_code} - {e.response.text}",
                    target_metadata={"status_code": e.response.status_code},
                    error=True
                )
            except Exception as e:
                return MCPTargetResponse(
                    raw_response=f"Connection Error: {str(e)}",
                    target_metadata={},
                    error=True
                )

# Global singleton instance to inject into graph nodes
mcp_client = MCPEnvironmentClient()