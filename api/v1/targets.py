import uuid
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database.sqlite_target_repo import target_repo

router = APIRouter(prefix="/api/v1/targets", tags=["Target Configurations"])

class TargetSystemSchema(BaseModel):
    id: Optional[str] = Field(None, description="Unique ID. Auto-generated if not provided.")
    name: str = Field(..., description="Human readable name for the target")
    description: Optional[str] = Field("", description="Brief description")
    target_type: str = Field("mock", description="Either 'mock' or 'external'")
    url: Optional[str] = Field("", description="The external API endpoint URL")
    system_prompt: Optional[str] = Field("", description="System instructions / context for mock")
    secret_token: Optional[str] = Field("", description="Crown jewel secret to exfiltrate")
    headers: Optional[str] = Field("{}", description="JSON string of HTTP headers")
    payload_field_name: Optional[str] = Field("query", description="The request JSON field to put payload in")
    use_llm: Optional[bool] = Field(False, description="Whether to simulate using a real LLM model")

@router.get("", response_model=List[TargetSystemSchema])
async def list_targets():
    """List all registered target systems."""
    return target_repo.list_targets()

@router.get("/{target_id}", response_model=TargetSystemSchema)
async def get_target(target_id: str):
    """Retrieve details of a specific target system."""
    target = target_repo.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target system not found")
    return target

@router.post("", response_model=TargetSystemSchema)
async def create_or_update_target(schema: TargetSystemSchema):
    """Create or update a target system configuration."""
    target_data = schema.model_dump()
    
    # Generate unique ID if none provided
    if not target_data.get("id"):
        target_data["id"] = f"target_{uuid.uuid4().hex[:12]}"
        
    # Validate headers are valid JSON
    try:
        json.loads(target_data.get("headers") or "{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for 'headers'")
        
    target_repo.save_target(target_data)
    return target_data

@router.delete("/{target_id}")
async def delete_target(target_id: str):
    """Delete a target system by ID."""
    target = target_repo.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target system not found")
    if target_id == "default_mock":
        raise HTTPException(status_code=400, detail="Cannot delete default mock target system")
    target_repo.delete_target(target_id)
    return {"message": f"Target system '{target_id}' successfully deleted."}

import asyncio
@router.get("/memory/exploits")
async def get_all_exploits():
    """Retrieve all successful exploit vectors stored in ChromaDB long-term memory."""
    from agents.memory import memory_manager
    try:
        def _get_all():
            return memory_manager.repo.collection.get()
        data = await asyncio.to_thread(_get_all)
        formatted = []
        if data and data.get('ids'):
            for i in range(len(data['ids'])):
                formatted.append({
                    "id": data['ids'][i],
                    "prompt": data['documents'][i],
                    "metadata": data['metadatas'][i] if data['metadatas'] else {}
                })
        return formatted
    except Exception as e:
        return [{"id": "error", "prompt": f"Could not retrieve memories: {str(e)}", "metadata": {}}]
