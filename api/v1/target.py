"""
FastAPI router for the Mock Target Environment.

The actual simulation logic lives in core/mock_target.py so it can be
imported by Celery workers without pulling in FastAPI dependencies.
"""
from fastapi import APIRouter
from core.mock_target import ChatRequest, ChatResponse, simulated_rag_chat

router = APIRouter(prefix="/api/v1/target", tags=["Mock Target Environment"])

# Re-export the Pydantic models so existing imports from this module keep working
__all__ = ["router", "ChatRequest", "ChatResponse", "simulated_rag_chat"]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    A dynamic simulated vulnerable Enterprise RAG API endpoint.
    Delegates to core.mock_target.simulated_rag_chat.
    """
    return await simulated_rag_chat(request)