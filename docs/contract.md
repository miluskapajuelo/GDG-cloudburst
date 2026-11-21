# SentinelDesk: Interface Contract

**Status:** frozen at T+0:30. To change it, follow the contract change process in [CLAUDE.md](../CLAUDE.md) (rule 1).

This file defines:
1. the HTTP API that the console calls (owner: A2)
2. the Python module interfaces that `api/` calls inside `agent/` and `ml/` (owners: A1, B1, B2)
3. the shared constants

A full example response is in [shared/fixtures/mock_triage_response.json](../shared/fixtures/mock_triage_response.json). The console and all mocks must match it field for field.

---

## 1. HTTP API (FastAPI, `http://localhost:8000`)

CORS must allow `http://localhost:5173` (Vite) and `http://localhost:8501` (Streamlit fallback).

### `GET /health`
```json
{ "status": "ok", "mock": false, "classifier_loaded": true, "index_size": 49440, "llm_configured": true, "llm_model": "claude-opus-5-5" }
```

### `GET /config`
Returns the current gate thresholds from `agent/config.py`, so the console can show them.
```json
{ "T_HIGH_PRIORITY_P": 0.35, "T_INCIDENT_P": 0.40, "T_CONF_TYPE": 0.45, "T_CONF_PRIORITY": 0.45, "T_CONF_QUEUE": 0.25, "T_SIM": 0.55, "TOP_K": 5, "BURST_SIM": 0.75, "BURST_MIN": 3, "BURST_WINDOW_MIN": 15 }
```

### `GET /metrics`
Returns the contents of `eval/results/metrics.json`. Returns `404` if the eval has not run yet. The console shows these numbers as a "Holdout metrics" strip. The shape is defined in [team-a-ml-eval.md](tasks/team-a-ml-eval.md) (task A2.6).

### `POST /triage`
Request:
```json
{ "subject": "VPN ausgefallen" , "body": "Seit 08:00 Uhr ..." }
```
- `subject` is optional. It may be missing, `null` or `""`.
- `body` is required. If it is empty or only whitespace, return `422`.
- If `body` is longer than 8,000 characters, truncate it (do not reject).

Query params:
- `skip_llm=true`: run everything except the LLM call (used by the eval). `draft` is `null`, and the gate skips the post-draft checks.

Response `200`:
```jsonc
{
  "request_id": "5d0c…",                    // uuid4 string
  "mock": false,                            // true only when SENTINEL_MOCK=1
  "input": { "subject": "VPN ausgefallen", "body_chars": 412, "truncated": false },

  "language": { "code": "de", "confidence": 0.99, "reply_language": "de" },
  // reply_language is "de" if code == "de", otherwise "en"

  "pii": { "masked": true, "counts": { "EMAIL": 1, "PHONE": 0, "IP": 1, "IBAN": 0, "CARD": 0, "ACCOUNT": 0 } },

  "predictions": {
    "type":     { "label": "Incident", "confidence": 0.82, "probs": { "Incident": 0.82, "Problem": 0.10, "Request": 0.05, "Change": 0.03 } },
    "queue":    { "label": "Technical Support", "confidence": 0.61, "probs": { "...": 0.0 } },
    "priority": { "label": "high", "confidence": 0.71, "probs": { "high": 0.71, "medium": 0.22, "low": 0.07 } }
  },
  // confidence == probs[label] == max(probs). probs sum to 1 (±0.01). Labels exactly as in the dataset.

  "escalation": {
    "status": "ESCALATE",                   // "ESCALATE" | "AUTO_DRAFT"
    "route": "ON_CALL",                     // "ON_CALL" | "HUMAN_REVIEW" | null (null iff AUTO_DRAFT)
    "badge": "Escalate to On-Call Engineer",// UI text: "Auto-Draft Ready" | "Escalate to On-Call Engineer" | "Human Review Required"
    "reasons": [
      { "code": "HIGH_PRIORITY_INCIDENT", "message": "Predicted high priority (p=0.71) and Incident (p=0.82)." }
    ]
  },
  // Reason codes, route logic and badge text: docs/escalation-policy.md

  "precedents": [
    {
      "ticket_id": "TKT-00412",
      "similarity": 0.81,                   // cosine, 0..1, sorted descending
      "language": "en",
      "subject": "VPN not connecting after update",   // may be ""
      "body_snippet": "first 300 chars of KB body…",
      "answer_snippet": "first 400 chars of KB answer…",
      "answer": "full KB answer (used by the UI expander)",
      "type": "Incident", "queue": "Technical Support", "priority": "high",
      "tags": ["VPN", "Network"]
    }
  ],
  // 0..TOP_K items. Always from the KB split only. Never from test.

  "draft": {
    "status": "OK",                         // "OK" | "INSUFFICIENT_EVIDENCE"
    "text": "Sehr geehrte Damen und Herren, … [TKT-00412] …",
    "cited_ids": ["TKT-00412", "TKT-01877"],// subset of precedents[].ticket_id (checked by validate_citations)
    "language": "de",
    "for_human_review": true,               // true when escalation.status == "ESCALATE"
    "model": "claude-opus-5-5"
  },
  // draft is null when: skip_llm=true, NO_PRECEDENT, PROMPT_INJECTION_SUSPECTED, or LLM_UNAVAILABLE

  "burst": {
    "active": true,
    "cluster_size": 4,
    "window_minutes": 15,
    "label": "VPN connection failures",
    "request_ids": ["…", "…"]
  },
  // when not active: { "active": false, "cluster_size": 1, "window_minutes": 15, "label": null, "request_ids": [] }

  "latency_ms": { "pii": 1, "language": 3, "classify": 9, "retrieve": 28, "gate": 1, "generate": 2140, "total": 2190 }
  // integers. "generate" is 0 when no LLM call was made. total is wall-clock for the whole request.
}
```

Errors: `422` for invalid input (FastAPI default body). `500` returns `{ "detail": "..." }`. The API must never return a 500 because the LLM failed. LLM failures become `LLM_UNAVAILABLE` in the escalation.

### `POST /burst/reset`
Clears the burst detector's memory (for demo resets). Returns `{ "ok": true }`.

### Mock mode
When `SENTINEL_MOCK=1`, `/triage` returns `shared/fixtures/mock_triage_response.json` with a fresh `request_id`, `"mock": true`, and `input` filled from the request. No models are loaded. **A2 ships this by T+0:30** so Team C is never blocked.

---

## 2. Python module interfaces

All functions are synchronous. Load models once at API startup (FastAPI lifespan), never per request.

### Shared: `shared/text.py` (A1, kickoff)
```python
def build_text(subject: str | None, body: str | None) -> str:
    """Return the subject and body joined with a blank line (empty subject is skipped).
    Strip whitespace. Treat NaN or None as "". Use the same function for training, indexing and inference."""
```

### A1: `ml/predict.py`
```python
class TriageClassifier:
    @classmethod
    def load(cls, path: str = "artifacts/clf.joblib") -> "TriageClassifier": ...
    def predict(self, text: str) -> dict:
        """Return {"type": Pred, "queue": Pred, "priority": Pred}
        where Pred = {"label": str, "confidence": float, "probs": dict[str, float]}."""
```

### B1: `agent/lang.py`
```python
def detect_language(text: str) -> dict:
    """Return {"code": "en"|"de"|<other ISO 639-1>, "confidence": float, "reply_language": "en"|"de"}."""
```

### B1: `agent/pii.py`
```python
def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace PII with [EMAIL] [PHONE] [IP] [IBAN] [CARD] [ACCOUNT].
    Return (masked_text, counts). The counts dict always has all 6 keys."""
```

### B1: `agent/retrieve.py`
```python
class Retriever:
    @classmethod
    def load(cls, index_dir: str = "artifacts") -> "Retriever": ...
    @property
    def size(self) -> int: ...
    def embed(self, text: str) -> "np.ndarray":   # shape (384,), float32, L2-normalised
        ...
    def search(self, vector: "np.ndarray", k: int = 5, exclude_ids: set[str] | None = None) -> list[dict]:
        """Return precedent dicts exactly as in the HTTP response, sorted by similarity descending.
        exclude_ids drops those KB tickets. Threshold tuning uses it to skip a validation ticket's self-match."""
```

### B1: `agent/burst.py`
```python
class BurstDetector:
    def __init__(self, sim_threshold: float, min_cluster: int, window_minutes: int): ...
    def observe(self, request_id: str, vector: "np.ndarray", summary: str, ts: float | None = None) -> dict:
        """Add the ticket to the window. Return the burst object as in the HTTP response."""
    def reset(self) -> None: ...
```

### B2: `agent/gate.py`
```python
def pre_draft_gate(predictions: dict, precedents: list[dict], text: str) -> dict:
    """Return {"reasons": list[Reason], "allow_draft": bool}
    where Reason = {"code": str, "message": str}."""

def finalize_escalation(pre: dict, draft: dict | None, citation_problems: list[str], llm_error: str | None) -> dict:
    """Return the escalation object as in the HTTP response."""
```

### B2: `agent/draft.py`
```python
def generate_draft(text: str, reply_language: str, precedents: list[dict], for_human_review: bool) -> dict:
    """Return the draft object as in the HTTP response.
    Raise DraftError on API failure or refusal (the pipeline turns it into LLM_UNAVAILABLE)."""
```

### B2: `agent/citations.py`
```python
def validate_citations(draft_text: str, cited_ids: list[str], allowed_ids: set[str]) -> list[str]:
    """Return a list of human-readable problems. An empty list means the draft passes."""
```

### B2: `agent/pipeline.py`
```python
class AgentPipeline:
    def __init__(self, retriever: Retriever, burst: BurstDetector): ...
    def run(self, request_id: str, text: str, language: dict, predictions: dict, *, skip_llm: bool = False) -> dict:
        """Return {"precedents", "escalation", "draft", "burst",
                   "latency_ms": {"retrieve", "gate", "generate"}}.
        `text` is already PII-masked."""
```

### A2: `api/service.py` (orchestrates the steps; `api/main.py` stays thin)
```python
def triage(subject: str | None, body: str, *, skip_llm: bool = False) -> dict:   # full response dict
```
The order is fixed: `build_text`, then `mask_pii`, then `detect_language`, then `classifier.predict(masked)`, then `pipeline.run(masked, …)`, then assemble. The eval script calls `api.service.triage` in-process, so it uses the exact code path of the live demo.

---

## 3. Shared constants

| Name | Values |
|---|---|
| `type` labels | `Incident`, `Request`, `Problem`, `Change` |
| `priority` labels | `high`, `medium`, `low` |
| `queue` labels | Taken from the training data. A1 writes them to `artifacts/labels.json` at train time. |
| Ticket ID format | `TKT-` + 5-digit zero-padded index after the seed-42 shuffle (see [data-and-leakage.md](data-and-leakage.md)) |
| Citation format in draft text | `[TKT-01234]`, with square brackets and the exact ID. Several IDs are written as `[TKT-01234][TKT-05678]`. |
| PII placeholders | `[EMAIL]` `[PHONE]` `[IP]` `[IBAN]` `[CARD]` `[ACCOUNT]` |
| Escalation reason codes | See [escalation-policy.md](escalation-policy.md) |
| Env vars | See [.env.example](../.env.example) |
