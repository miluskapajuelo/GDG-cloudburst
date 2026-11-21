"""A2.2 tests: api.service orchestrator and the progressive-wiring stubs in api.stubs.

Run: python -m pytest tests/test_a2_service.py -q

No network and no sentence-transformers. The forced-stub tests point SENTINEL_ARTIFACTS_DIR at an
empty folder and block the agent.retrieve, agent.pipeline and agent.gate imports, so the stub
retriever, stub pipeline and stub gate are used whatever exists on disk. The real-classifier test
copies clf.joblib into a temp folder (skipped when it has not been trained yet).
"""
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

import api.service as service
from api import stubs

REPO = Path(__file__).resolve().parents[1]
REAL_ART = Path(os.getenv("SENTINEL_ARTIFACTS_DIR", REPO / "artifacts"))  # read before any monkeypatch

CONTRACT_KEYS = ["request_id", "mock", "input", "language", "pii", "predictions", "escalation",
                 "precedents", "draft", "burst", "latency_ms"]
LATENCY_KEYS = ["pii", "language", "classify", "retrieve", "gate", "generate", "total"]
BADGES = {"ON_CALL": "Escalate to On-Call Engineer", "HUMAN_REVIEW": "Human Review Required",
          None: "Auto-Draft Ready"}
BLOCKED = ("agent.retrieve", "agent.pipeline", "agent.gate")


def _block_heavy_modules(monkeypatch):
    for mod in BLOCKED:
        monkeypatch.setitem(sys.modules, mod, None)  # `import mod` now raises ImportError


@pytest.fixture
def stub_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_ARTIFACTS_DIR", str(tmp_path))
    _block_heavy_modules(monkeypatch)
    service._reset()
    yield tmp_path
    service._reset()


def _check_predictions(predictions, queue_count=10):
    assert set(predictions) == {"type", "queue", "priority"}
    assert set(predictions["type"]["probs"]) == {"Incident", "Request", "Problem", "Change"}
    assert set(predictions["priority"]["probs"]) == {"high", "medium", "low"}
    assert len(predictions["queue"]["probs"]) == queue_count
    for head, pred in predictions.items():
        probs = pred["probs"]
        assert abs(sum(probs.values()) - 1.0) < 0.01, head
        assert pred["confidence"] == probs[pred["label"]] == max(probs.values()), head


def _check_escalation(esc):
    codes = [r["code"] for r in esc["reasons"]]
    assert esc["status"] == ("ESCALATE" if codes else "AUTO_DRAFT")
    expected_route = "ON_CALL" if "HIGH_PRIORITY_INCIDENT" in codes else ("HUMAN_REVIEW" if codes else None)
    assert esc["route"] == expected_route
    assert esc["badge"] == BADGES[expected_route]
    if "HIGH_PRIORITY_INCIDENT" in codes:
        assert codes[0] == "HIGH_PRIORITY_INCIDENT"
    assert all(r["message"] for r in esc["reasons"])
    return codes


def test_import_is_cheap():
    code = ("import sys, api.service; "
            "print(','.join(m for m in ('sklearn', 'torch', 'sentence_transformers', 'faiss', 'lingua') "
            "if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == ""


def test_status_before_startup_loads_nothing(stub_env):
    st = service.status()
    assert st["classifier_loaded"] is False and st["index_size"] == 0 and st["llm_model"] is None
    service.reset_burst()  # no-op, must not raise or load anything
    assert service._state is None


def test_forced_stub_full_response(stub_env):
    st_before = "sentence_transformers" in sys.modules
    body = "Nobody can connect to the VPN since 8am."
    r = service.triage("VPN down", body)

    assert list(r) == CONTRACT_KEYS
    assert r["mock"] is False
    uuid.UUID(r["request_id"])
    assert r["input"] == {"subject": "VPN down", "body_chars": len(body), "truncated": False}
    assert set(r["language"]) == {"code", "confidence", "reply_language"}
    _check_predictions(r["predictions"])
    assert r["precedents"] == [] and r["draft"] is None
    assert r["burst"] == {"active": False, "cluster_size": 1, "window_minutes": 15, "label": None,
                          "request_ids": []}
    assert list(r["latency_ms"]) == LATENCY_KEYS
    assert all(type(v) is int and v >= 0 for v in r["latency_ms"].values())
    assert r["latency_ms"]["generate"] == 0
    if not st_before:
        assert "sentence_transformers" not in sys.modules


def test_status_reports_stubs(stub_env):
    service.startup()
    st = service.status()
    assert set(st) == {"classifier_loaded", "index_size", "llm_configured", "llm_model", "components"}
    assert st["components"] == {"pii": "real", "language": "real", "classifier": "stub",
                                "retriever": "stub", "burst": "real", "pipeline": "stub"}
    assert st["classifier_loaded"] is False
    assert st["index_size"] == 0
    assert st["llm_configured"] is False and st["llm_model"] is None


def test_startup_is_idempotent(stub_env):
    service.startup()
    first = service._state
    service.startup()
    assert service._state is first


def test_stub_escalation_consistent_with_status(stub_env):
    r = service.triage(None, "Our invoice shows a wrong amount.")
    codes = _check_escalation(r["escalation"])
    # Stub classifier (uniform probs) and stub retriever (no KB): human review, never on-call, no draft.
    assert "NO_PRECEDENT" in codes and "LOW_CLASSIFIER_CONFIDENCE" in codes
    assert "HIGH_PRIORITY_INCIDENT" not in codes
    assert r["escalation"]["route"] == "HUMAN_REVIEW"
    assert r["draft"] is None


def test_truncation_and_body_chars(stub_env, monkeypatch):
    seen = []
    real_build_text = service.build_text
    monkeypatch.setattr(service, "build_text", lambda s, b: seen.append(b) or real_build_text(s, b))

    r = service.triage("Long one", "a" * 9000)
    assert r["input"] == {"subject": "Long one", "body_chars": 9000, "truncated": True}
    assert len(seen[-1]) == service.MAX_BODY_CHARS

    r = service.triage(None, "b" * 8000)
    assert r["input"] == {"subject": "", "body_chars": 8000, "truncated": False}
    assert len(seen[-1]) == 8000


@pytest.mark.parametrize("body", ["", "   \n\t ", None])
def test_empty_body_raises(stub_env, body):
    with pytest.raises(ValueError):
        service.triage("subject", body)


def test_pii_counts(stub_env):
    r = service.triage("Login", "Please reset my account, mail me at jane.doe@example.com")
    assert list(r["pii"]["counts"]) == list(stubs.PII_KEYS)
    assert r["pii"]["counts"]["EMAIL"] == 1 and r["pii"]["masked"] is True
    r = service.triage("Login", "Please reset my password")
    assert r["pii"]["masked"] is False and set(r["pii"]["counts"].values()) == {0}


def test_get_config_env_override(monkeypatch):
    monkeypatch.setenv("SENTINEL_T_SIM", "0.61")
    monkeypatch.setenv("SENTINEL_TOP_K", "7")
    monkeypatch.setenv("SENTINEL_T_CONF_QUEUE", "not-a-number")
    cfg = service.get_config()
    assert list(cfg) == list(stubs.DEFAULT_CONFIG)
    assert cfg["T_SIM"] == 0.61 and type(cfg["T_SIM"]) is float
    assert cfg["TOP_K"] == 7 and type(cfg["TOP_K"]) is int
    assert type(cfg["T_CONF_QUEUE"]) is float  # invalid override ignored, no crash


def test_burst_detector_built_from_config(stub_env, monkeypatch):
    monkeypatch.setenv("SENTINEL_BURST_WINDOW_MIN", "20")
    body = "VPN gateway handshake timeout for all remote staff"
    results = [service.triage("VPN timeout", body) for _ in range(3)]
    assert [b["burst"]["window_minutes"] for b in results] == [20, 20, 20]
    # The real BurstDetector runs on the stub retriever's hashed vectors: identical tickets cluster.
    assert results[2]["burst"]["active"] is True and results[2]["burst"]["cluster_size"] == 3
    service.reset_burst()
    assert service.triage("VPN timeout", body)["burst"]["active"] is False


def test_stub_gate_rules():
    cfg = stubs.DEFAULT_CONFIG
    confident = {
        "type": {"label": "Incident", "confidence": 0.8, "probs": {"Incident": 0.8, "Request": 0.1, "Problem": 0.05, "Change": 0.05}},
        "queue": {"label": "IT Support", "confidence": 0.6, "probs": {"IT Support": 0.6, "Technical Support": 0.4}},
        "priority": {"label": "high", "confidence": 0.7, "probs": {"high": 0.7, "medium": 0.2, "low": 0.1}},
    }
    pre = stubs.stub_pre_draft_gate(confident, [], "text", cfg)
    assert [r["code"] for r in pre["reasons"]] == ["HIGH_PRIORITY_INCIDENT", "NO_PRECEDENT"]
    assert pre["allow_draft"] is False
    assert "p=0.70" in pre["reasons"][0]["message"] and "p=0.80" in pre["reasons"][0]["message"]
    esc = stubs.stub_finalize_escalation(pre, None, [], None)
    assert (esc["status"], esc["route"]) == ("ESCALATE", "ON_CALL")
    _check_escalation(esc)

    calm = dict(confident, priority={"label": "low", "confidence": 0.7, "probs": {"high": 0.1, "medium": 0.2, "low": 0.7}})
    pre = stubs.stub_pre_draft_gate(calm, [{"similarity": 0.9}], "text", cfg)
    assert pre == {"reasons": [], "allow_draft": True}
    esc = stubs.stub_finalize_escalation(pre, None, [], None)
    assert esc == {"status": "AUTO_DRAFT", "route": None, "badge": "Auto-Draft Ready", "reasons": []}

    pre = stubs.stub_pre_draft_gate(calm, [{"similarity": 0.4}], "text", cfg)
    assert [r["code"] for r in pre["reasons"]] == ["NO_PRECEDENT"] and "0.40" in pre["reasons"][0]["message"]


def test_stub_classifier_uses_labels_json(tmp_path):
    (tmp_path / "labels.json").write_text('{"queue": ["Zeta Queue", "Technical Support"]}', encoding="utf-8")
    labels = stubs.load_label_sets(tmp_path)
    assert labels["queue"] == ["Technical Support", "Zeta Queue"]
    _check_predictions(stubs.StubClassifier(labels).predict("x"), queue_count=2)
    _check_predictions(stubs.StubClassifier(stubs.load_label_sets(None)).predict("x"))


@pytest.mark.skipif(not (REAL_ART / "clf.joblib").is_file(), reason="classifier not trained yet")
def test_real_classifier(tmp_path, monkeypatch):
    for name in ("clf.joblib", "labels.json"):
        if (REAL_ART / name).is_file():
            shutil.copy(REAL_ART / name, tmp_path / name)
    monkeypatch.setenv("SENTINEL_ARTIFACTS_DIR", str(tmp_path))
    _block_heavy_modules(monkeypatch)
    service._reset()
    try:
        service.startup()
        st = service.status()
        assert st["components"]["classifier"] == "real" and st["classifier_loaded"] is True
        r = service.triage("VPN down for the whole office", "Since 8am nobody can connect to the VPN.")
        _check_predictions(r["predictions"])
        _check_escalation(r["escalation"])
    finally:
        service._reset()
