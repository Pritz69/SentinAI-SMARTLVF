from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

class AdversarialPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    payload_id: str = Field(..., description="Unique deterministic execution hash")
    raw_prompt: str = Field(..., description="The semantic text of the attack vector")
    attack_vector_type: str = Field(..., description="Category: indirect_injection, token_smuggling, RAG_poisoning")
    obfuscation_applied: List[str] = Field(default_factory=list, description="Array of transformations applied")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RiskEvaluation(BaseModel):
    score: float = Field(..., description="Normalized risk vector score between 0.0 and 1.0")
    vulnerabilities_detected: List[str] = Field(default_factory=list)
    is_compromised: bool = Field(default=False)
    leakage_detected: Optional[str] = Field(default=None, description="Extracted sensitive PII/tokens from target output")
    reasoning: str = Field(..., description="Deep structural analysis justification from evaluator")
    risk_matrix: Dict[str, float] = Field(default_factory=dict, description="Risk sub-scores (info_disclosure, prompt_injection, guardrail_bypass)")
    refusal_detected: bool = Field(default=False, description="Whether the target system successfully refused the malicious prompt")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)