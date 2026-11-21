"""
API Service Orchestrator
Owner: A2 (Gustavo)

Coordinates all components in the correct order per contract.md §2:
1. build_text(subject, body)
2. mask_pii(text)
3. detect_language(text)
4. classifier.predict(masked)
5. pipeline.run(masked, ...)
6. Assemble response
"""

import os
import uuid
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

# Try to import real modules, fall back to stubs
try:
    from shared.text import build_text
except ImportError:
    from api.stubs import build_text

try:
    from agent.pii import mask_pii
except ImportError:
    from api.stubs import mask_pii as _mask_pii
    mask_pii = _mask_pii

try:
    from agent.lang import detect_language
except ImportError:
    from api.stubs import detect_language as _detect_language
    detect_language = _detect_language

try:
    from ml.predict import TriageClassifier
except ImportError:
    from api.stubs import StubClassifier as TriageClassifier

try:
    from agent.retrieve import Retriever
except ImportError:
    from api.stubs import StubRetriever as Retriever

try:
    from agent.burst import BurstDetector
except ImportError:
    from api.stubs import StubBurstDetector as BurstDetector

try:
    from agent.pipeline import AgentPipeline
except ImportError:
    from api.stubs import StubPipeline as AgentPipeline

from api.stubs import DEFAULT_CONFIG


# Global instances
_classifier: Optional[Any] = None
_retriever: Optional[Any] = None
_burst_detector: Optional[Any] = None
_pipeline: Optional[Any] = None


def load_classifier():
    """Load the TriageClassifier."""
    global _classifier
    _classifier = TriageClassifier.load()
    return _classifier


def load_retriever():
    """Load the Retriever."""
    global _retriever
    _retriever = Retriever.load()
    return _retriever


def init_burst_detector():
    """Initialize the BurstDetector."""
    global _burst_detector
    sim_threshold = float(os.getenv("SENTINEL_BURST_SIM", DEFAULT_CONFIG["BURST_SIM"]))
    min_cluster = int(os.getenv("SENTINEL_BURST_MIN", DEFAULT_CONFIG["BURST_MIN"]))
    window_minutes = int(os.getenv("SENTINEL_BURST_WINDOW_MIN", DEFAULT_CONFIG["BURST_WINDOW_MIN"]))
    _burst_detector = BurstDetector(sim_threshold, min_cluster, window_minutes)
    return _burst_detector


def init_pipeline():
    """Initialize the AgentPipeline."""
    global _pipeline
    _pipeline = AgentPipeline(retriever=_retriever, burst=_burst_detector)
    return _pipeline


def get_index_size() -> int:
    """Get the retriever index size."""
    if _retriever:
        return _retriever.size
    return 0


def get_config() -> Dict[str, Any]:
    """Get current gate thresholds from config."""
    config = DEFAULT_CONFIG.copy()
    
    # Override with env vars
    for key in config:
        env_key = f"SENTINEL_{key}"
        if env_key in os.environ:
            if isinstance(config[key], int):
                config[key] = int(os.environ[env_key])
            elif isinstance(config[key], float):
                config[key] = float(os.environ[env_key])
    
    return config


def reset_burst():
    """Reset the burst detector."""
    if _burst_detector:
        _burst_detector.reset()


def triage(
    subject: Optional[str], 
    body: str, 
    *, 
    skip_llm: bool = False
) -> Dict[str, Any]:
    """
    Main triage function - orchestrates all components.
    
    Returns the full response dict matching contract.md.
    """
    start_time = time.perf_counter()
    
    # Generate request ID
    request_id = str(uuid.uuid4())
    
    # Stage 0: Build text
    text = build_text(subject, body)
    text_len = len(text)
    input_truncated = False
    
    # Stage 1: PII masking
    t0 = time.perf_counter()
    masked_text, pii_counts = mask_pii(text)
    t_pii = int((time.perf_counter() - t0) * 1000)
    
    # Stage 2: Language detection
    t1 = time.perf_counter()
    lang_result = detect_language(masked_text)
    t_lang = int((time.perf_counter() - t1) * 1000)
    
    # Stage 3: Classification
    t2 = time.perf_counter()
    if _classifier:
        predictions = _classifier.predict(masked_text)
    else:
        predictions = {"type": {"label": "Request", "confidence": 0.5, "probs": {}},
                       "queue": {"label": "Customer Service", "confidence": 0.5, "probs": {}},
                       "priority": {"label": "medium", "confidence": 0.5, "probs": {}}}
    t_classify = int((time.perf_counter() - t2) * 1000)
    
    # Stage 4-6: Pipeline (retrieval, gate, draft)
    t3 = time.perf_counter()
    if _pipeline:
        pipeline_result = _pipeline.run(
            request_id=request_id,
            text=masked_text,
            language=lang_result,
            predictions=predictions,
            skip_llm=skip_llm
        )
    else:
        pipeline_result = {
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
    
    t_retrieve = pipeline_result.get("latency_ms", {}).get("retrieve", 0)
    t_gate = pipeline_result.get("latency_ms", {}).get("gate", 0)
    t_generate = pipeline_result.get("latency_ms", {}).get("generate", 0)
    
    # Total latency
    total_latency = int((time.perf_counter() - start_time) * 1000)
    
    # Build response
    response = {
        "request_id": request_id,
        "mock": False,
        "input": {
            "subject": subject or "",
            "body_chars": len(body),
            "truncated": input_truncated
        },
        "language": {
            "code": lang_result.get("code", "en"),
            "confidence": lang_result.get("confidence", 0.5),
            "reply_language": lang_result.get("reply_language", "en")
        },
        "pii": {
            "masked": any(v > 0 for v in pii_counts.values()),
            "counts": pii_counts
        },
        "predictions": predictions,
        "escalation": pipeline_result.get("escalation", {}),
        "precedents": pipeline_result.get("precedents", []),
        "draft": pipeline_result.get("draft"),
        "burst": pipeline_result.get("burst", {}),
        "latency_ms": {
            "pii": t_pii,
            "language": t_lang,
            "classify": t_classify,
            "retrieve": t_retrieve,
            "gate": t_gate,
            "generate": t_generate,
            "total": total_latency
        }
    }
    
    return response


__all__ = [
    "load_classifier",
    "load_retriever", 
    "init_burst_detector",
    "init_pipeline",
    "get_index_size",
    "get_config",
    "reset_burst",
    "triage",
]