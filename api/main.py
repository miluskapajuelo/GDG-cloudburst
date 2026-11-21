"""SentinelDesk HTTP API (FastAPI). Owner: A2.

Run:       uvicorn api.main:app --port 8000
Mock mode: SENTINEL_MOCK=1 uvicorn api.main:app --port 8000   (no models, no api.service import)

This module stays thin. All real work lives in api/service.py, which is imported
lazily so that mock mode never touches it and a missing service gives 503, not a crash.
Endpoints that call sync service code are plain `def` so FastAPI runs them in its
threadpool and a slow LLM call never blocks /health.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import ConfigResponse, HealthResponse, TriageRequest, TriageResponse

REPO_ROOT = Path(__file__).resolve().parents[1]
MOCK_FIXTURE_PATH = REPO_ROOT / "shared" / "fixtures" / "mock_triage_response.json"
METRICS_PATH = REPO_ROOT / "eval" / "results" / "metrics.json"
MAX_BODY_CHARS = 8000

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
]

# agent/config.py defaults (tuned, B2.7); /config returns these in mock mode (nothing is loaded there).
MOCK_CONFIG: dict[str, Any] = {
    "T_HIGH_PRIORITY_P": 0.20, "T_INCIDENT_P": 0.30, "T_CONF_TYPE": 0.50, "T_CONF_PRIORITY": 0.50,
    "T_CONF_QUEUE": 0.25, "T_SIM": 0.55, "TOP_K": 5, "BURST_SIM": 0.65, "BURST_MIN": 3, "BURST_WINDOW_MIN": 15,
}

HEALTH_DEFAULTS: dict[str, Any] = {
    "status": "ok", "mock": False, "classifier_loaded": False,
    "index_size": 0, "llm_configured": False, "llm_model": None,
}

log = logging.getLogger("uvicorn.error")


def is_mock_mode() -> bool:
    """Read at call time so tests (and restarts) can flip it."""
    return os.getenv("SENTINEL_MOCK", "0").strip() == "1"


def _ascii(obj: object) -> str:
    """Log-safe text: Windows cp1252 consoles crash on non-ASCII when output is piped."""
    return str(obj).encode("ascii", "replace").decode("ascii")


class ServiceUnavailable(Exception):
    pass


def _service() -> ModuleType:
    """Import api.service lazily. Raise ServiceUnavailable if it cannot be imported."""
    try:
        return importlib.import_module("api.service")
    except Exception as exc:  # ImportError, or an error raised while importing it
        raise ServiceUnavailable(f"api.service unavailable: {type(exc).__name__}: {exc}") from exc


def _require_service() -> ModuleType:
    try:
        return _service()
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if is_mock_mode():
        log.info("SentinelDesk API: MOCK mode (SENTINEL_MOCK=1), no models loaded")
    else:
        try:
            _service().startup()
            log.info("SentinelDesk API: service started")
        except ServiceUnavailable as exc:
            log.warning("SentinelDesk API: %s. /triage, /config, /burst/reset will return 503.", _ascii(exc))
        except Exception as exc:  # startup() should never raise; keep serving /health if it does
            log.error("SentinelDesk API: service.startup() failed: %s", _ascii(exc))
    yield


app = FastAPI(
    title="SentinelDesk API",
    description="Multilingual ticket triage with an escalation gate, RAG precedents and grounded drafts.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, response_model_exclude_unset=True)
def health() -> dict[str, Any]:
    if is_mock_mode():
        return {**HEALTH_DEFAULTS, "mock": True}
    try:
        status = dict(_service().status())
        merged = {**HEALTH_DEFAULTS, **status, "status": "ok", "mock": False}
        return HealthResponse.model_validate(merged).model_dump(exclude_unset=True)
    except ServiceUnavailable:  # already logged once at startup; /health is polled
        return dict(HEALTH_DEFAULTS)
    except Exception as exc:  # /health must always answer 200
        log.warning("health: service.status() failed: %s", _ascii(exc))
        return dict(HEALTH_DEFAULTS)


@app.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    if is_mock_mode():
        return ConfigResponse.model_validate(MOCK_CONFIG)
    svc = _require_service()
    try:
        return ConfigResponse.model_validate(svc.get_config())
    except Exception as exc:
        log.exception("config failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/metrics")
def get_metrics() -> dict[str, Any]:
    path = METRICS_PATH  # module global, looked up per call (tests patch it)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="metrics.json not found. Run: python -m eval.run_eval")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"could not read metrics.json: {exc}") from exc


def _mock_triage(req: TriageRequest, *, skip_llm: bool = False) -> TriageResponse:
    data = json.loads(MOCK_FIXTURE_PATH.read_text(encoding="utf-8"))
    data["request_id"] = str(uuid.uuid4())
    data["mock"] = True
    data["input"] = {
        "subject": req.subject or "",
        "body_chars": len(req.body),  # length as received, before truncation
        "truncated": len(req.body) > MAX_BODY_CHARS,
    }
    if skip_llm:  # contract: no LLM call -> draft is null and generate is 0
        lat = data["latency_ms"]
        lat["total"] = max(0, lat["total"] - lat["generate"])
        lat["generate"] = 0
        data["draft"] = None
    return TriageResponse.model_validate(data)


@app.post("/triage", response_model=TriageResponse)
def triage(
    req: TriageRequest,
    skip_llm: bool = Query(False, description="Run everything except the LLM call (draft is null)."),
) -> TriageResponse:
    if is_mock_mode():
        try:
            return _mock_triage(req, skip_llm=skip_llm)
        except Exception as exc:
            log.exception("mock triage failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    svc = _require_service()
    try:
        # Raw body: service.triage truncates to 8000 chars and fills `input` itself.
        result = svc.triage(req.subject, req.body, skip_llm=skip_llm)
        return TriageResponse.model_validate(result)
    except Exception as exc:
        log.exception("triage failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/burst/reset")
def burst_reset() -> dict[str, bool]:
    if is_mock_mode():
        return {"ok": True}
    svc = _require_service()
    try:
        svc.reset_burst()
    except Exception as exc:
        log.exception("burst reset failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
