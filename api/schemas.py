"""
Pydantic v2 schemas for SentinelDesk API.
Matches contract.md exactly.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# Request models
class TriageRequest(BaseModel):
    subject: Optional[str] = Field(None, description="Ticket subject line (optional)")
    body: str = Field(..., description="Ticket body (required)", min_length=1)


# Nested response models
class LanguageInfo(BaseModel):
    code: str = Field(..., description="ISO 639-1 language code")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reply_language: str = Field(..., description="en or de")


class PIIInfo(BaseModel):
    masked: bool
    counts: Dict[str, int] = Field(
        default_factory=lambda: {
            "EMAIL": 0, "PHONE": 0, "IP": 0, 
            "IBAN": 0, "CARD": 0, "ACCOUNT": 0
        }
    )


class PredictionHead(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    probs: Dict[str, float]


class Predictions(BaseModel):
    type: PredictionHead
    queue: PredictionHead
    priority: PredictionHead


class EscalationReason(BaseModel):
    code: str
    message: str


class Escalation(BaseModel):
    status: str = Field(..., description="ESCALATE or AUTO_DRAFT")
    route: Optional[str] = Field(None, description="ON_CALL, HUMAN_REVIEW, or null")
    badge: str
    reasons: List[EscalationReason] = Field(default_factory=list)


class Precedent(BaseModel):
    ticket_id: str
    similarity: float = Field(..., ge=0.0, le=1.0)
    language: str
    subject: str
    body_snippet: str
    answer_snippet: str
    answer: str
    type: str
    queue: str
    priority: str
    tags: List[str] = Field(default_factory=list)


class Draft(BaseModel):
    status: str = Field(..., description="OK or INSUFFICIENT_EVIDENCE")
    text: str
    cited_ids: List[str] = Field(default_factory=list)
    language: str
    for_human_review: bool
    model: str


class BurstInfo(BaseModel):
    active: bool
    cluster_size: int = 1
    window_minutes: int = 15
    label: Optional[str] = None
    request_ids: List[str] = Field(default_factory=list)


class LatencyMs(BaseModel):
    pii: int = 0
    language: int = 0
    classify: int = 0
    retrieve: int = 0
    gate: int = 0
    generate: int = 0
    total: int = 0


class InputInfo(BaseModel):
    subject: Optional[str]
    body_chars: int
    truncated: bool = False


# Main response model
class TriageResponse(BaseModel):
    request_id: str
    mock: bool = False
    input: InputInfo
    language: LanguageInfo
    pii: PIIInfo
    predictions: Predictions
    escalation: Escalation
    precedents: List[Precedent] = Field(default_factory=list)
    draft: Optional[Draft] = None
    burst: BurstInfo
    latency_ms: LatencyMs


# Health response
class HealthResponse(BaseModel):
    status: str
    mock: bool = False
    classifier_loaded: bool = False
    index_size: int = 0
    llm_configured: bool = False
    llm_model: Optional[str] = None


# Config response
class ConfigResponse(BaseModel):
    T_HIGH_PRIORITY_P: float
    T_INCIDENT_P: float
    T_CONF_TYPE: float
    T_CONF_PRIORITY: float
    T_CONF_QUEUE: float
    T_SIM: float
    TOP_K: int
    BURST_SIM: float
    BURST_MIN: int
    BURST_WINDOW_MIN: int