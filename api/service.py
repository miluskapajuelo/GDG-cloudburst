"""Service orchestrator: the one code path behind POST /triage and the holdout eval.

Owner: A2. `api/main.py` stays thin and calls into this module; `eval/run_eval.py` calls
`triage()` in-process, so the eval measures exactly what the demo runs.

Fixed order (docs/contract.md section 2):
    build_text -> mask_pii -> detect_language(masked) -> classifier.predict(masked)
    -> pipeline.run(request_id, masked, ...) -> assemble the response

Progressive wiring: `startup()` loads each real module and falls back to its stub in
`api/stubs.py` per component, on ImportError or on any load failure (for example a missing
artifact). `status()` reports which components are real.

Importing this module is cheap: no models load and no heavy library is imported until
`startup()` runs (`/config` in mock mode imports it).

Smoke test:  python -m api.service
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from api import stubs
from shared.text import build_text  # pure Python, cheap to import

log = logging.getLogger("sentinel.service")

MAX_BODY_CHARS = 8000
DEFAULT_LLM_MODEL = "gemini-3.5-flash-lite"
COMPONENTS = ("pii", "language", "classifier", "retriever", "burst", "pipeline")

_lock = threading.Lock()
_state: dict[str, Any] | None = None  # set once by startup(); see _load_components()


def _artifacts_dir() -> Path:
    return Path(os.getenv("SENTINEL_ARTIFACTS_DIR", "artifacts"))


def _ascii(text: object) -> str:
    """Log/print-safe text: Windows cp1252 consoles crash on some characters when piped."""
    return str(text).encode("ascii", "replace").decode("ascii")


def _ms(seconds: float) -> int:
    return int(round(seconds * 1000))


# --- config -----------------------------------------------------------------------------------------

def get_config() -> dict:
    """The 10 gate/burst thresholds of contract GET /config.

    Values come from agent/config.py (B2) when it can be imported, else from the defaults in
    docs/escalation-policy.md section 4. A `SENTINEL_<KEY>` env var overrides each one.
    """
    try:
        import agent.config as agent_config
    except Exception:  # ImportError, or any error inside B2's module
        agent_config = None

    cfg: dict[str, float | int] = {}
    for key, default in stubs.DEFAULT_CONFIG.items():
        kind = type(default)
        value: Any = getattr(agent_config, key, default) if agent_config is not None else default
        raw = os.getenv(f"SENTINEL_{key}")
        if raw is not None and raw.strip():
            value = raw.strip()
        try:
            cfg[key] = kind(float(value)) if kind is int else kind(value)
        except (TypeError, ValueError):
            log.warning("Ignoring invalid value for %s: %s", key, _ascii(value))
            cfg[key] = default
    return cfg


# --- startup ----------------------------------------------------------------------------------------

def _load_components() -> dict[str, Any]:
    """Load every component, falling back to its stub one at a time. Never raises."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    art = _artifacts_dir()
    cfg = get_config()
    kinds: dict[str, str] = {}
    errors: dict[str, str] = {}

    def fallback(name: str, exc: BaseException) -> None:
        kinds[name] = "stub"
        errors[name] = _ascii(f"{type(exc).__name__}: {exc}")[:200]
        log.warning("Component %s: using stub (%s)", name, errors[name])

    try:
        from agent.pii import mask_pii
        kinds["pii"] = "real"
    except Exception as exc:
        mask_pii = stubs.mask_pii
        fallback("pii", exc)

    try:
        from agent.lang import detect_language
        kinds["language"] = "real"
    except Exception as exc:
        detect_language = stubs.detect_language
        fallback("language", exc)

    # Import order: scikit-learn (classifier) first, then sentence-transformers/torch, then faiss
    # (inside agent.retrieve). See agent/NOTES.md.
    try:
        clf_path = art / "clf.joblib"
        if not clf_path.is_file():
            raise FileNotFoundError(f"{clf_path} not found (run python -m ml.train)")
        from ml.predict import TriageClassifier

        classifier: Any = TriageClassifier.load(str(clf_path))
        kinds["classifier"] = "real"
    except Exception as exc:
        classifier = stubs.StubClassifier(stubs.load_label_sets(art))
        fallback("classifier", exc)

    try:
        # Check the index files first, so a missing index never imports torch or loads the model.
        for name in ("kb.faiss", "kb_meta.parquet"):
            if not (art / name).is_file():
                raise FileNotFoundError(f"{art / name} not found (run python -m agent.build_index)")
        from agent.retrieve import Retriever

        retriever: Any = Retriever.load(str(art))
        kinds["retriever"] = "real"
    except Exception as exc:
        retriever = stubs.StubRetriever()
        fallback("retriever", exc)

    burst_args = (cfg["BURST_SIM"], cfg["BURST_MIN"], cfg["BURST_WINDOW_MIN"])
    try:
        from agent.burst import BurstDetector

        burst: Any = BurstDetector(*burst_args)
        kinds["burst"] = "real"
    except Exception as exc:
        burst = stubs.StubBurstDetector(*burst_args)
        fallback("burst", exc)

    try:
        from agent.pipeline import AgentPipeline

        pipeline: Any = AgentPipeline(retriever, burst)
        kinds["pipeline"] = "real"
    except Exception as exc:
        pipeline = stubs.StubPipeline(retriever, burst, config=get_config)
        fallback("pipeline", exc)

    return {
        "mask_pii": mask_pii,
        "detect_language": detect_language,
        "classifier": classifier,
        "retriever": retriever,
        "burst": burst,
        "pipeline": pipeline,
        "components": {name: kinds[name] for name in COMPONENTS},
        "errors": errors,
    }


def startup() -> None:
    """Load each real module or fall back to its stub, then run one warm-up triage.

    Idempotent and thread-safe. Never raises: a failed component becomes a stub, and a failed
    warm-up is logged.
    """
    global _state
    with _lock:
        if _state is not None:
            return
        t0 = time.perf_counter()
        _state = _load_components()
        log.info("Components: %s (loaded in %d ms)", _state["components"], _ms(time.perf_counter() - t0))

    try:
        triage("warmup", "warm up", skip_llm=True)
    except Exception as exc:
        log.warning("Warm-up triage failed: %s", _ascii(f"{type(exc).__name__}: {exc}"))
    finally:
        reset_burst()  # the warm-up ticket must not count towards a burst


def _reset() -> None:
    """Forget all loaded components (tests only). The next triage() or startup() reloads them."""
    global _state
    with _lock:
        _state = None


# --- status / burst ---------------------------------------------------------------------------------

def status() -> dict:
    """Readiness info for GET /health. Never loads models: before startup() every component
    reports "stub" and nothing is loaded."""
    state = _state
    if state is None:
        return {"classifier_loaded": False, "index_size": 0, "llm_configured": False, "llm_model": None,
                "components": {name: "stub" for name in COMPONENTS}}
    components = dict(state["components"])
    llm_configured = components["pipeline"] == "real" and bool(os.getenv("GEMINI_API_KEY", "").strip())
    try:
        index_size = int(state["retriever"].size)
    except Exception:
        index_size = 0
    return {
        "classifier_loaded": components["classifier"] == "real",
        "index_size": index_size,
        "llm_configured": llm_configured,
        "llm_model": (os.getenv("SENTINEL_LLM_MODEL", "").strip() or DEFAULT_LLM_MODEL) if llm_configured else None,
        "components": components,
    }


def reset_burst() -> None:
    """Clear the burst detector's window (POST /burst/reset). No-op before startup()."""
    state = _state
    if state is not None:
        state["burst"].reset()


# --- triage -----------------------------------------------------------------------------------------

def triage(subject: str | None, body: str, *, skip_llm: bool = False) -> dict:
    """Run one ticket through the full pipeline and return the contract response dict.

    `body` is the raw body as received; bodies over 8000 characters are truncated here.
    Raises ValueError when the body is empty or whitespace only. Calls startup() if needed.
    """
    if not isinstance(body, str) or not body.strip():
        raise ValueError("body must be a non-empty string")
    startup()
    state = _state
    assert state is not None

    t_start = time.perf_counter()
    request_id = str(uuid.uuid4())
    subject_str = subject if isinstance(subject, str) else ""
    body_chars = len(body)
    truncated = body_chars > MAX_BODY_CHARS
    text = build_text(subject_str, body[:MAX_BODY_CHARS])

    t0 = time.perf_counter()
    masked, raw_counts = state["mask_pii"](text)
    counts = {k: int(raw_counts.get(k, 0)) for k in stubs.PII_KEYS}
    t_pii = time.perf_counter() - t0

    t0 = time.perf_counter()
    lang = state["detect_language"](masked)
    code = str(lang.get("code") or "en")
    language = {"code": code, "confidence": float(lang.get("confidence") or 0.0),
                "reply_language": "de" if code == "de" else "en"}
    t_lang = time.perf_counter() - t0

    t0 = time.perf_counter()
    predictions = state["classifier"].predict(masked)
    t_classify = time.perf_counter() - t0

    # Without real PII masking, ticket text must never reach the external LLM (CLAUDE.md rule 5).
    if state["components"]["pii"] != "real":
        skip_llm = True
    result = state["pipeline"].run(request_id, masked, language, predictions, skip_llm=skip_llm)
    stage = result.get("latency_ms") or {}

    return {
        "request_id": request_id,
        "mock": False,
        "input": {"subject": subject_str, "body_chars": body_chars, "truncated": truncated},
        "language": language,
        "pii": {"masked": any(v > 0 for v in counts.values()), "counts": counts},
        "predictions": predictions,
        "escalation": result["escalation"],
        "precedents": result.get("precedents") or [],
        "draft": result.get("draft"),
        "burst": result["burst"],
        "latency_ms": {
            "pii": _ms(t_pii),
            "language": _ms(t_lang),
            "classify": _ms(t_classify),
            "retrieve": int(round(stage.get("retrieve", 0))),
            "gate": int(round(stage.get("gate", 0))),
            "generate": int(round(stage.get("generate", 0))),
            "total": _ms(time.perf_counter() - t_start),
        },
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    t0 = time.perf_counter()
    startup()
    print(f"startup + warm-up: {_ms(time.perf_counter() - t0)} ms")
    print("status:", _ascii(status()))
    if _state is not None and _state["components"]["pipeline"] == "stub":
        print("gate:", _state["pipeline"].gate)

    tickets = [
        ("VPN down for the whole office",
         "Since 8am nobody can connect to the VPN. Production work is blocked, please help urgently. "
         "Contact me at jane.doe@example.com."),
        ("VPN ausgefallen",
         "Seit heute Morgen kann sich niemand mehr mit dem VPN verbinden. Bitte dringend helfen, "
         "das ganze Team ist betroffen."),
    ]
    for subject, body in tickets:
        r = triage(subject, body, skip_llm=True)
        print()
        print(f"[{r['request_id'][:8]}] subject={_ascii(subject)!r} input={r['input']}")
        print("  language:", r["language"])
        print("  pii:", r["pii"])
        print("  predictions:", {h: (p["label"], round(p["confidence"], 2)) for h, p in r["predictions"].items()})
        e = r["escalation"]
        print(f"  escalation: {e['status']} route={e['route']} badge={e['badge']!r}")
        for reason in e["reasons"]:
            print(f"    - {reason['code']}: {_ascii(reason['message'])}")
        print(f"  precedents: {len(r['precedents'])}  draft: {r['draft']}  burst active: {r['burst']['active']}")
        print("  latency_ms:", r["latency_ms"])

    long_body = "x " * 5000
    r = triage(None, long_body, skip_llm=True)
    assert r["input"] == {"subject": "", "body_chars": 10000, "truncated": True}, r["input"]
    print("\ntruncation OK:", r["input"])
    print("api.service OK")
