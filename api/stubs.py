"""Contract-shaped stand-ins for modules that are missing or failed to load (progressive wiring).

Owner: A2. `api.service.startup()` loads each real module and falls back to the stub here,
one component at a time, so Team A never blocks on Team B. `/health` reports which parts are
real. Every stub returns data in exactly the shape of docs/contract.md.

This module must stay cheap to import: stdlib only at the top level (numpy is imported lazily).
"""
from __future__ import annotations

import json
import re
import time
import zlib
from pathlib import Path
from typing import Any, Callable

# Fallback defaults, kept in sync with agent/config.py (B2.7 tuned values). The real config overrides them.
DEFAULT_CONFIG: dict[str, float | int] = {
    "T_HIGH_PRIORITY_P": 0.20,
    "T_INCIDENT_P": 0.30,
    "T_CONF_TYPE": 0.50,
    "T_CONF_PRIORITY": 0.50,
    "T_CONF_QUEUE": 0.25,
    "T_SIM": 0.55,
    "TOP_K": 5,
    "BURST_SIM": 0.65,
    "BURST_MIN": 3,
    "BURST_WINDOW_MIN": 15,
}

PII_KEYS: tuple[str, ...] = ("EMAIL", "PHONE", "IP", "IBAN", "CARD", "ACCOUNT")
EMBED_DIM = 384

# Label sets (contract section 3). The first label of each head is its KB majority class
# (ml/EDA.md), so the stub's tie-break picks the majority class.
TYPE_LABELS = ["Incident", "Request", "Problem", "Change"]
PRIORITY_LABELS = ["medium", "high", "low"]
QUEUE_LABELS = [
    "Technical Support", "Product Support", "Customer Service", "IT Support", "Billing and Payments",
    "Returns and Exchanges", "Service Outages and Maintenance", "Sales and Pre-Sales",
    "Human Resources", "General Inquiry",
]

BADGES = {
    "ON_CALL": "Escalate to On-Call Engineer",
    "HUMAN_REVIEW": "Human Review Required",
    None: "Auto-Draft Ready",
}
_RULE_ORDER = [
    "PROMPT_INJECTION_SUSPECTED", "HIGH_PRIORITY_INCIDENT", "LOW_CLASSIFIER_CONFIDENCE", "NO_PRECEDENT",
    "UNSUPPORTED_REQUEST", "LLM_INSUFFICIENT_EVIDENCE", "CITATION_CHECK_FAILED", "LLM_UNAVAILABLE",
]
_NO_DRAFT_CODES = {"PROMPT_INJECTION_SUSPECTED", "NO_PRECEDENT"}


def inactive_burst(window_minutes: int) -> dict:
    return {"active": False, "cluster_size": 1, "window_minutes": int(window_minutes), "label": None,
            "request_ids": []}


# --- B1 stand-ins ---------------------------------------------------------------------------------

def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """Stub: masks nothing. api.service forces skip_llm=True while this stub is active, so
    unmasked text never reaches an external LLM."""
    return text or "", {k: 0 for k in PII_KEYS}


def detect_language(text: str) -> dict:
    """Stub: always English with zero confidence."""
    return {"code": "en", "confidence": 0.0, "reply_language": "en"}


class StubRetriever:
    """Stands in for agent.retrieve.Retriever when the FAISS index or the embedding model is missing.

    There is no KB, so search() is always empty and the gate raises NO_PRECEDENT. embed() returns
    a hashed bag-of-words vector (384 dims, L2-normalised), so a real BurstDetector or a real
    AgentPipeline can still use it.
    """

    size = 0

    def embed(self, text: str) -> Any:
        import numpy as np

        vec = np.zeros(EMBED_DIM, dtype=np.float32)
        for tok in re.findall(r"[^\W\d_]{3,}", (text or "").lower()):
            vec[zlib.crc32(tok.encode("utf-8")) % EMBED_DIM] += 1.0
        norm = float(np.linalg.norm(vec))
        if norm == 0.0:
            vec[0] = 1.0
        else:
            vec /= norm
        return vec

    def search(self, vector: Any, k: int = 5, exclude_ids: set[str] | None = None) -> list[dict]:
        return []


class StubBurstDetector:
    """Stands in for agent.burst.BurstDetector: never active."""

    def __init__(self, sim_threshold: float = 0.65, min_cluster: int = 3, window_minutes: int = 15):
        self.window_minutes = int(window_minutes)

    def observe(self, request_id: str, vector: Any, summary: str, ts: float | None = None) -> dict:
        return inactive_burst(self.window_minutes)

    def reset(self) -> None:
        pass


# --- A1 stand-in ------------------------------------------------------------------------------------

def load_label_sets(artifacts_dir: Path | None) -> dict[str, list[str]]:
    """Real label sets, with queues from artifacts/labels.json when A1's training has written it."""
    labels = {"type": list(TYPE_LABELS), "queue": list(QUEUE_LABELS), "priority": list(PRIORITY_LABELS)}
    if artifacts_dir is not None:
        try:
            queues = json.loads((Path(artifacts_dir) / "labels.json").read_text(encoding="utf-8"))["queue"]
            if queues:
                # Keep the majority-first order for queues we know, then append any others.
                labels["queue"] = [q for q in QUEUE_LABELS if q in queues] + [q for q in queues if q not in QUEUE_LABELS]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return labels


class StubClassifier:
    """Stands in for ml.predict.TriageClassifier: uniform probabilities ("the stub knows nothing").

    The output is contract-shaped: confidence == probs[label] == max(probs), and probs sum to 1.
    Uniform probabilities keep rule 2 (HIGH_PRIORITY_INCIDENT) quiet and make rule 3
    (LOW_CLASSIFIER_CONFIDENCE) fire, so every ticket goes to human review.
    """

    def __init__(self, labels: dict[str, list[str]] | None = None):
        self.labels = labels or load_label_sets(None)

    def predict(self, text: str) -> dict:
        out: dict[str, dict] = {}
        for head in ("type", "queue", "priority"):
            names = self.labels[head]
            p = 1.0 / len(names)
            out[head] = {"label": names[0], "confidence": p, "probs": {n: p for n in names}}
        return out


# --- B2 stand-ins -----------------------------------------------------------------------------------
# STUB GATE: a small subset of docs/escalation-policy.md (rules 2, 3 and 4 plus the final decision).
# B2's agent/gate.py replaces it automatically as soon as it can be imported.

def stub_pre_draft_gate(predictions: dict, precedents: list[dict], text: str, cfg: dict) -> dict:
    reasons: list[dict] = []

    p_high = float(predictions["priority"]["probs"].get("high", 0.0))
    p_inc = float(predictions["type"]["probs"].get("Incident", 0.0))
    if p_high >= cfg["T_HIGH_PRIORITY_P"] and p_inc >= cfg["T_INCIDENT_P"]:
        reasons.append({"code": "HIGH_PRIORITY_INCIDENT",
                        "message": f"Predicted high priority (p={p_high:.2f}) and Incident (p={p_inc:.2f})."})

    low = []
    for head, key in (("type", "T_CONF_TYPE"), ("priority", "T_CONF_PRIORITY"), ("queue", "T_CONF_QUEUE")):
        conf = float(predictions[head]["confidence"])
        if conf < cfg[key]:
            low.append(f"{head} {conf:.2f} < {cfg[key]:.2f}")
    if low:
        reasons.append({"code": "LOW_CLASSIFIER_CONFIDENCE",
                        "message": "Low classifier confidence: " + ", ".join(low) + "."})

    if not precedents:
        reasons.append({"code": "NO_PRECEDENT", "message": "No similar past ticket was found in the knowledge base."})
    elif float(precedents[0]["similarity"]) < cfg["T_SIM"]:
        reasons.append({"code": "NO_PRECEDENT",
                        "message": f"Best precedent similarity {float(precedents[0]['similarity']):.2f} "
                                   f"is below T_SIM {cfg['T_SIM']:.2f}."})

    return {"reasons": reasons, "allow_draft": not any(r["code"] in _NO_DRAFT_CODES for r in reasons)}


def final_decision(reasons: list[dict]) -> dict:
    """The "Final decision" block of docs/escalation-policy.md section 1."""
    ordered = sorted(reasons, key=lambda r: (r["code"] != "HIGH_PRIORITY_INCIDENT",
                                             _RULE_ORDER.index(r["code"]) if r["code"] in _RULE_ORDER else 99))
    status = "ESCALATE" if ordered else "AUTO_DRAFT"
    route = ("ON_CALL" if any(r["code"] == "HIGH_PRIORITY_INCIDENT" for r in ordered)
             else ("HUMAN_REVIEW" if ordered else None))
    return {"status": status, "route": route, "badge": BADGES[route], "reasons": ordered}


def stub_finalize_escalation(pre: dict, draft: dict | None, citation_problems: list[str],
                             llm_error: str | None) -> dict:
    """The stub pipeline never drafts, so phase 2 adds nothing."""
    return final_decision(list(pre["reasons"]))


def _ms(seconds: float) -> int:
    return int(round(seconds * 1000))


class StubPipeline:
    """Stands in for agent.pipeline.AgentPipeline (B2). No LLM: draft is always None, generate = 0.

    It still uses whatever retriever and burst detector loaded (real or stub): embed once,
    search(k=TOP_K), burst.observe(). The gate is B2's agent.gate when it can be imported,
    otherwise the stub gate above.
    """

    def __init__(self, retriever: Any, burst: Any, config: Callable[[], dict] | None = None):
        self.retriever = retriever
        self.burst = burst
        self._config = config or (lambda: dict(DEFAULT_CONFIG))
        try:
            from agent.gate import finalize_escalation, pre_draft_gate

            self._pre = lambda preds, precs, text, cfg: pre_draft_gate(preds, precs, text)
            self._finalize = finalize_escalation
            self.gate = "real"
        except Exception:  # ImportError, or any error inside B2's module
            self._pre = stub_pre_draft_gate
            self._finalize = stub_finalize_escalation
            self.gate = "stub"

    def run(self, request_id: str, text: str, language: dict, predictions: dict, *,
            skip_llm: bool = False) -> dict:
        cfg = self._config()

        t0 = time.perf_counter()
        vector = self.retriever.embed(text)
        precedents = self.retriever.search(vector, k=int(cfg["TOP_K"]))
        burst = self.burst.observe(request_id, vector, summary=text[:200])
        t_retrieve = time.perf_counter() - t0

        t0 = time.perf_counter()
        pre = self._pre(predictions, precedents, text, cfg)
        escalation = self._finalize(pre, None, [], None)
        t_gate = time.perf_counter() - t0

        return {
            "precedents": precedents,
            "escalation": escalation,
            "draft": None,
            "burst": burst,
            "latency_ms": {"retrieve": _ms(t_retrieve), "gate": _ms(t_gate), "generate": 0},
        }
