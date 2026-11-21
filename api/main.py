"""
SentinelDesk API - FastAPI server
Owner: A2 (Gustavo)
"""

import os
import uuid
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Schemas
from api.schemas import (
    TriageRequest, TriageResponse,
    HealthResponse, ConfigResponse
)

# Service
from api import service

# Mock fixture path
MOCK_FIXTURE_PATH = Path(__file__).parent.parent / "shared" / "fixtures" / "mock_triage_response.json"

# Mock mode flag - checked at runtime for each request
def is_mock_mode() -> bool:
    return os.getenv("SENTINEL_MOCK", "0") == "1"

# Global state
classifier_loaded = False
index_loaded = False
llm_configured = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models at startup."""
    global classifier_loaded, index_loaded, llm_configured
    
    print("🚀 Starting SentinelDesk API...")
    
    if not is_mock_mode():
        try:
            # Load classifier (A1)
            service.load_classifier()
            classifier_loaded = True
            print("✅ Classifier loaded")
        except Exception as e:
            print(f"⚠️  Classifier load failed: {e}")
        
        try:
            # Load retriever (B1)
            service.load_retriever()
            index_loaded = True
            print("✅ Retriever loaded")
        except Exception as e:
            print(f"⚠️  Retriever load failed: {e}")
        
        try:
            # Initialize burst detector
            service.init_burst_detector()
            print("✅ Burst detector initialized")
        except Exception as e:
            print(f"⚠️  Burst detector init failed: {e}")
        
        try:
            # Initialize agent pipeline
            service.init_pipeline()
            llm_configured = True
            print("✅ Agent pipeline initialized")
        except Exception as e:
            print(f"⚠️  Agent pipeline init failed: {e}")
        
        # Warm-up request
        try:
            service.triage("warmup", "warm up", skip_llm=True)
            print("✅ Warm-up complete")
        except Exception as e:
            print(f"⚠️  Warm-up failed: {e}")
    else:
        print("📦 Running in MOCK mode (models not loaded)")
    
    yield
    
    print("🛑 Shutting down SentinelDesk API...")


# Create FastAPI app
app = FastAPI(
    title="SentinelDesk API",
    description="Autonomous Incident Triage & Grounded Resolution Copilot",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        mock=is_mock_mode(),
        classifier_loaded=classifier_loaded,
        index_size=service.get_index_size() if index_loaded else 0,
        llm_configured=llm_configured,
        llm_model=os.getenv("SENTINEL_LLM_MODEL", "gemini-3.5-flash-lite") if llm_configured else None
    )


@app.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get current gate thresholds."""
    config = service.get_config()
    return ConfigResponse(**config)


@app.get("/metrics")
async def get_metrics():
    """Get evaluation metrics."""
    metrics_path = Path("eval/results/metrics.json")
    
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="Metrics not found. Run eval first.")
    
    with open(metrics_path) as f:
        metrics = json.load(f)
    
    return metrics


@app.post("/triage", response_model=TriageResponse)
async def triage(request: TriageRequest, skip_llm: bool = Query(False)):
    """
    Main triage endpoint.
    
    Process a ticket through:
    1. PII masking
    2. Language detection
    3. Classification (type, queue, priority)
    4. RAG retrieval
    5. Escalation gate
    6. Draft generation (optional)
    """
    # Validate input
    body = request.body
    if not body or not body.strip():
        raise HTTPException(status_code=422, detail="body is required and cannot be empty")
    
    # Truncate if too long
    truncated = False
    if len(body) > 8000:
        body = body[:8000]
        truncated = True
    
    subject = request.subject
    
    # Mock mode
    if is_mock_mode():
        with open(MOCK_FIXTURE_PATH) as f:
            mock_response = json.load(f)
        
        # Update with request-specific data
        mock_response["request_id"] = str(uuid.uuid4())
        mock_response["mock"] = True
        mock_response["input"] = {
            "subject": subject or "",
            "body_chars": len(request.body),
            "truncated": truncated
        }
        
        return TriageResponse(**mock_response)
    
    # Real processing
    try:
        result = service.triage(subject, body, skip_llm=skip_llm)
        return TriageResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/burst/reset")
async def burst_reset():
    """Reset burst detector memory."""
    service.reset_burst()
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)