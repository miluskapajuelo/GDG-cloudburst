"""A2.1 tests: api.main (HTTP layer) and api.schemas. Run: python -m pytest tests/test_a2_api.py -q

No network, no models. The real api.service is never used here: tests either block it
(sys.modules entry = None -> ImportError) or swap in a small fake module, so they behave
the same before and after A2.2 merges.
"""
from __future__ import annotations

import json
import sys
import types
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app
from api.schemas import TriageResponse

FIXTURE = Path(__file__).resolve().parents[1] / "shared" / "fixtures" / "mock_triage_response.json"
CONFIG = dict(api_main.MOCK_CONFIG)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def no_service(monkeypatch):
    """Make `import api.service` fail, whether or not the file exists."""
    monkeypatch.setitem(sys.modules, "api.service", None)


@pytest.fixture
def mock_client(monkeypatch, no_service):
    monkeypatch.setenv("SENTINEL_MOCK", "1")
    with TestClient(app) as c:  # runs the lifespan too: it must not need api.service
        yield c


@pytest.fixture
def real_client_no_service(monkeypatch, no_service):
    monkeypatch.setenv("SENTINEL_MOCK", "0")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fake_service(monkeypatch):
    calls: dict = {"startup": 0, "reset": 0, "triage": []}
    mod = types.ModuleType("api.service")

    def startup() -> None:
        calls["startup"] += 1

    def status() -> dict:
        return {"classifier_loaded": True, "index_size": 42, "llm_configured": False, "llm_model": None,
                "components": {"pii": "real", "language": "real", "classifier": "real",
                               "retriever": "stub", "burst": "stub", "pipeline": "stub"}}

    def get_config() -> dict:
        return dict(CONFIG)

    def reset_burst() -> None:
        calls["reset"] += 1

    def triage(subject, body, *, skip_llm=False) -> dict:
        calls["triage"].append((subject, body, skip_llm))
        if body == "boom":
            raise RuntimeError("pipeline exploded")
        data = _fixture()
        data["mock"] = False
        data["input"] = {"subject": subject or "", "body_chars": len(body), "truncated": len(body) > 8000}
        if skip_llm:
            data["draft"] = None
        return data

    for fn in (startup, status, get_config, reset_burst, triage):
        setattr(mod, fn.__name__, fn)
    monkeypatch.setitem(sys.modules, "api.service", mod)
    monkeypatch.setenv("SENTINEL_MOCK", "0")
    return calls


# ------------------------------------------------------------------ schemas

def test_fixture_validates_against_schema():
    data = _fixture()
    model = TriageResponse.model_validate(data)
    dumped = model.model_dump(mode="json")
    assert set(dumped) == set(data)
    assert dumped["escalation"] == data["escalation"]
    assert dumped["precedents"][0]["ticket_id"] == "TKT-00412"


def test_similarity_slightly_above_one_is_accepted():
    data = _fixture()
    data["precedents"][0]["similarity"] = 1.0000001
    data["predictions"]["type"]["confidence"] = 1.0000001
    TriageResponse.model_validate(data)


# ------------------------------------------------------------------ mock /triage

def test_mock_triage_returns_fixture(mock_client):
    r = mock_client.post("/triage", json={"subject": "VPN down", "body": "test"})
    assert r.status_code == 200
    got, fx = r.json(), _fixture()
    assert got["mock"] is True
    assert got["escalation"] == fx["escalation"]
    assert got["draft"]["text"] == fx["draft"]["text"]  # UTF-8 read: umlauts intact on Windows
    assert [p["ticket_id"] for p in got["precedents"]] == [p["ticket_id"] for p in fx["precedents"]]
    assert got["request_id"] != fx["request_id"]


def test_mock_request_ids_are_fresh_uuid4(mock_client):
    a = mock_client.post("/triage", json={"body": "test"}).json()["request_id"]
    b = mock_client.post("/triage", json={"body": "test"}).json()["request_id"]
    assert a != b
    assert uuid.UUID(a).version == 4


def test_mock_input_filled_from_request(mock_client):
    r = mock_client.post("/triage", json={"subject": "VPN ausgefallen", "body": "Seit 08:00 Uhr"})
    assert r.json()["input"] == {"subject": "VPN ausgefallen", "body_chars": 14, "truncated": False}


@pytest.mark.parametrize("payload", [{"body": ""}, {"body": "   \n\t "}, {"subject": "x"}, {"body": None}])
def test_blank_or_missing_body_is_422(mock_client, payload):
    r = mock_client.post("/triage", json=payload)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list) and detail[0]["loc"][-1] == "body"  # FastAPI default shape


@pytest.mark.parametrize("payload", [{"subject": None, "body": "hi"}, {"body": "hi"}, {"subject": "", "body": "hi"}])
def test_subject_optional(mock_client, payload):
    r = mock_client.post("/triage", json=payload)
    assert r.status_code == 200
    assert r.json()["input"]["subject"] == ""


def test_long_body_truncated_flag(mock_client):
    r = mock_client.post("/triage", json={"body": "a" * 8001})
    assert r.status_code == 200
    assert r.json()["input"] == {"subject": "", "body_chars": 8001, "truncated": True}
    r = mock_client.post("/triage", json={"body": "a" * 8000})
    assert r.json()["input"]["truncated"] is False


# ------------------------------------------------------------------ mock other endpoints

def test_mock_health(mock_client):
    r = mock_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mock": True, "classifier_loaded": False,
                        "index_size": 0, "llm_configured": False, "llm_model": None}


def test_mock_config_and_burst_reset(mock_client):
    assert mock_client.get("/config").json() == CONFIG
    assert mock_client.post("/burst/reset").json() == {"ok": True}


def test_metrics_404_when_missing(mock_client, monkeypatch, tmp_path):
    monkeypatch.setattr(api_main, "METRICS_PATH", tmp_path / "nope" / "metrics.json")
    r = mock_client.get("/metrics")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_metrics_returns_file(mock_client, monkeypatch, tmp_path):
    p = tmp_path / "metrics.json"
    p.write_text(json.dumps({"n_test": 3, "split_fingerprint": "abc"}), encoding="utf-8")
    monkeypatch.setattr(api_main, "METRICS_PATH", p)
    assert mock_client.get("/metrics").json() == {"n_test": 3, "split_fingerprint": "abc"}


def test_metrics_path_is_repo_relative():
    assert api_main.METRICS_PATH == Path(__file__).resolve().parents[1] / "eval" / "results" / "metrics.json"


def test_cors_preflight(mock_client):
    headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
               "Access-Control-Request-Headers": "content-type"}
    r = mock_client.options("/triage", headers=headers)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    bad = mock_client.options("/triage", headers={**headers, "Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


# ------------------------------------------------------------------ non-mock, api.service missing

def test_no_service_config_triage_reset_503(real_client_no_service):
    c = real_client_no_service
    for r in (c.get("/config"), c.post("/triage", json={"body": "test"}), c.post("/burst/reset")):
        assert r.status_code == 503
        assert "api.service" in r.json()["detail"]


def test_no_service_health_still_200(real_client_no_service):
    r = real_client_no_service.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mock": False, "classifier_loaded": False,
                        "index_size": 0, "llm_configured": False, "llm_model": None}


# ------------------------------------------------------------------ non-mock, fake api.service

def test_service_wiring(fake_service):
    with TestClient(app) as c:
        assert fake_service["startup"] == 1  # lifespan called service.startup()

        h = c.get("/health").json()
        assert h["mock"] is False and h["index_size"] == 42 and h["components"]["retriever"] == "stub"

        assert c.get("/config").json() == CONFIG
        assert c.post("/burst/reset").json() == {"ok": True} and fake_service["reset"] == 1

        body = "b" * 9000
        r = c.post("/triage?skip_llm=true", json={"subject": None, "body": body})
        assert r.status_code == 200
        assert r.json()["mock"] is False and r.json()["draft"] is None
        assert fake_service["triage"][-1] == (None, body, True)  # raw body, untruncated, skip_llm passed

        c.post("/triage", json={"body": "x"})
        assert fake_service["triage"][-1][2] is False


def test_service_exception_is_500_detail(fake_service):
    with TestClient(app) as c:
        r = c.post("/triage", json={"body": "boom"})
        assert r.status_code == 500
        assert r.json() == {"detail": "pipeline exploded"}


def test_health_survives_status_error(fake_service, monkeypatch):
    def broken_status() -> dict:
        raise RuntimeError("status broke")

    monkeypatch.setattr(sys.modules["api.service"], "status", broken_status)
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["mock"] is False and r.json()["classifier_loaded"] is False
