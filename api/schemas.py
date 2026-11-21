"""Pydantic v2 models for the SentinelDesk HTTP API.

Owner: A2. Mirrors docs/contract.md section 1 field for field.
Probability/similarity floats have no upper bound on purpose: FAISS and float
math can return 1.0000001, and that must not turn a good response into a 500.
"""
from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def _none_to_empty(v: Any) -> Any:
    """Map None / NaN (pandas missing value) to "" for string fields that 'may be ""'."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return v


# ---------------------------------------------------------------- request

class TriageRequest(BaseModel):
    subject: str | None = None
    body: str

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, v: str) -> str:
        # Raising ValueError here gives FastAPI's default 422 body.
        if not v.strip():
            raise ValueError("body must not be empty or whitespace")
        return v


# ---------------------------------------------------------------- response parts

class InputInfo(BaseModel):
    subject: str = ""
    body_chars: int
    truncated: bool = False

    @field_validator("subject", mode="before")
    @classmethod
    def subject_none_to_empty(cls, v: Any) -> Any:
        return _none_to_empty(v)


class LanguageInfo(BaseModel):
    code: str
    confidence: float
    reply_language: str  # "en" | "de"


class PIIInfo(BaseModel):
    masked: bool
    counts: dict[str, int]  # always the 6 keys EMAIL PHONE IP IBAN CARD ACCOUNT


class Pred(BaseModel):
    label: str
    confidence: float
    probs: dict[str, float]


class Predictions(BaseModel):
    type: Pred
    queue: Pred
    priority: Pred


class Reason(BaseModel):
    code: str
    message: str


class Escalation(BaseModel):
    status: Literal["ESCALATE", "AUTO_DRAFT"]
    route: Literal["ON_CALL", "HUMAN_REVIEW"] | None = None  # null iff AUTO_DRAFT
    badge: str  # "Auto-Draft Ready" | "Escalate to On-Call Engineer" | "Human Review Required"
    reasons: list[Reason] = Field(default_factory=list)


class Precedent(BaseModel):
    ticket_id: str
    similarity: float
    language: str
    subject: str = ""
    body_snippet: str
    answer_snippet: str
    answer: str
    type: str
    queue: str
    priority: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("subject", mode="before")
    @classmethod
    def subject_none_to_empty(cls, v: Any) -> Any:
        return _none_to_empty(v)


class Draft(BaseModel):
    status: Literal["OK", "INSUFFICIENT_EVIDENCE"]
    text: str
    cited_ids: list[str] = Field(default_factory=list)
    language: str
    for_human_review: bool
    model: str


class Burst(BaseModel):
    active: bool
    cluster_size: int = 1
    window_minutes: int = 15
    label: str | None = None
    request_ids: list[str] = Field(default_factory=list)


class LatencyMs(BaseModel):
    pii: int = 0
    language: int = 0
    classify: int = 0
    retrieve: int = 0
    gate: int = 0
    generate: int = 0
    total: int = 0


class TriageResponse(BaseModel):
    request_id: str
    mock: bool = False
    input: InputInfo
    language: LanguageInfo
    pii: PIIInfo
    predictions: Predictions
    escalation: Escalation
    precedents: list[Precedent] = Field(default_factory=list)
    draft: Draft | None = None  # null for skip_llm, NO_PRECEDENT, PROMPT_INJECTION_SUSPECTED, LLM_UNAVAILABLE
    burst: Burst
    latency_ms: LatencyMs


# ---------------------------------------------------------------- other endpoints

class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    mock: bool = False
    classifier_loaded: bool = False
    index_size: int = 0
    llm_configured: bool = False
    llm_model: str | None = None
    # Extra (optional) vs contract: which parts are real vs stub (A2.2). Absent in mock mode.
    components: dict[str, str] | None = None


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
