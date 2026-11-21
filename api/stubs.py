"""
Stubs for when modules are not yet available.
Used for progressive wiring - never blocks the API.
"""

import os
from typing import Any, Dict, List, Optional


# Default config from escalation-policy.md
DEFAULT_CONFIG = {
    "T_HIGH_PRIORITY_P": 0.35,
    "T_INCIDENT_P": 0.40,
    "T_CONF_TYPE": 0.45,
    "T_CONF_PRIORITY": 0.45,
    "T_CONF_QUEUE": 0.25,
    "T_SIM": 0.55,
    "TOP_K": 5,
    "BURST_SIM": 0.75,
    "BURST_MIN": 3,
    "BURST_WINDOW_MIN": 15,
}


class StubClassifier:
    """Stub for TriageClassifier when not loaded."""
    
    def predict(self, text: str) -> Dict[str, Any]:
        return {
            "type": {"label": "Request", "confidence": 0.5, "probs": {"Incident": 0.25, "Request": 0.25, "Problem": 0.25, "Change": 0.25}},
            "queue": {"label": "Customer Service", "confidence": 0.5, "probs": {"Customer Service": 0.2, "Technical Support": 0.2, "Billing and Payments": 0.2, "Product Support": 0.2, "IT Support": 0.1, "Sales and Pre-Sales": 0.1}},
            "priority": {"label": "medium", "confidence": 0.5, "probs": {"high": 0.33, "medium": 0.34, "low": 0.33}},
        }
    
    @classmethod
    def load(cls, path: str = "artifacts/clf.joblib"):
        raise ImportError("Classifier not available")


class StubRetriever:
    """Stub for Retriever when not loaded."""
    
    @property
    def size(self) -> int:
        return 0
    
    def search(self, vector: Any, k: int = 5, exclude_ids: Optional[set] = None) -> List[Dict]:
        return []
    
    def embed(self, text: str):
        raise ImportError("Retriever not available")
    
    @classmethod
    def load(cls, index_dir: str = "artifacts"):
        raise ImportError("Retriever not available")


class StubBurstDetector:
    """Stub for BurstDetector when not initialized."""
    
    def observe(self, request_id: str, vector: Any, summary: str, ts: Optional[float] = None) -> Dict:
        return {"active": False, "cluster_size": 1, "window_minutes": 15, "label": None, "request_ids": []}
    
    def reset(self) -> None:
        pass


class StubPipeline:
    """Stub for AgentPipeline when not initialized."""
    
    def run(self, request_id: str, text: str, language: Dict, predictions: Dict, *, skip_llm: bool = False) -> Dict:
        return {
            "precedents": [],
            "escalation": {
                "status": "AUTO_DRAFT",
                "route": None,
                "badge": "Auto-Draft Ready",
                "reasons": []
            },
            "draft": None,
            "burst": {"active": False, "cluster_size": 1, "window_minutes": 15, "label": None, "request_ids": []},
            "latency_ms": {"retrieve": 0, "gate": 0, "generate": 0}
        }


def mask_pii(text: str) -> tuple[str, Dict[str, int]]:
    """Stub PII masker."""
    return text, {"EMAIL": 0, "PHONE": 0, "IP": 0, "IBAN": 0, "CARD": 0, "ACCOUNT": 0}


def detect_language(text: str) -> Dict[str, Any]:
    """Stub language detector."""
    return {"code": "en", "confidence": 0.5, "reply_language": "en"}


def build_text(subject: Optional[str], body: Optional[str]) -> str:
    """Build text from subject and body."""
    parts = []
    if subject:
        parts.append(subject.strip())
    if body:
        parts.append(body.strip())
    return "\n\n".join(parts)


__all__ = [
    "StubClassifier",
    "StubRetriever", 
    "StubBurstDetector",
    "StubPipeline",
    "DEFAULT_CONFIG",
    "mask_pii",
    "detect_language",
    "build_text",
]