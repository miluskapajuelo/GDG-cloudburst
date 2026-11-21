import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import pipeline


class FakeRetriever:
    def __init__(self, precedents):
        self.precedents = precedents

    def embed(self, text):
        assert text == "Masked ticket text"
        return (1.0, 0.0)

    def search(self, vector, k):
        assert vector == (1.0, 0.0)
        assert k == pipeline.config.TOP_K
        return self.precedents


class FakeBurstDetector:
    def __init__(self, result):
        self.result = result

    def observe(self, request_id, vector, summary):
        assert (request_id, vector, summary) == ("request-id", (1.0, 0.0), "Masked ticket text")
        return self.result


@pytest.fixture
def case():
    fixture = Path(__file__).resolve().parents[1] / "shared/fixtures/mock_triage_response.json"
    mock = json.loads(fixture.read_text(encoding="utf-8"))
    agent = pipeline.AgentPipeline(FakeRetriever(mock["precedents"]), FakeBurstDetector(mock["burst"]))
    return agent, mock


def test_skip_llm_uses_pre_gate_only(monkeypatch, case):
    agent, mock = case
    monkeypatch.setattr(pipeline, "generate_draft", lambda *a, **kw: pytest.fail("Unexpected LLM call"))
    result = agent.run("request-id", "Masked ticket text", mock["language"], mock["predictions"], skip_llm=True)
    assert result["draft"] is None
    assert result["latency_ms"]["generate"] == 0
    assert [reason["code"] for reason in result["escalation"]["reasons"]] == ["HIGH_PRIORITY_INCIDENT"]
    assert result["precedents"] == mock["precedents"]
    assert result["burst"] == mock["burst"]


def test_llm_failure_preserves_on_call_route(monkeypatch, case):
    agent, mock = case

    def fail(text, reply_language, precedents, for_human_review):
        assert (text, reply_language, precedents, for_human_review) == (
            "Masked ticket text", "de", mock["precedents"], True,
        )
        raise pipeline.DraftError("Draft service timed out.")

    monkeypatch.setattr(pipeline, "generate_draft", fail)
    result = agent.run("request-id", "Masked ticket text", mock["language"], mock["predictions"])
    assert result["draft"] is None
    assert result["escalation"]["route"] == "ON_CALL"
    assert [reason["code"] for reason in result["escalation"]["reasons"]] == [
        "HIGH_PRIORITY_INCIDENT", "LLM_UNAVAILABLE",
    ]


def test_unexpected_generation_error_escalates_without_provider_details(monkeypatch, case):
    agent, mock = case
    mock["predictions"]["priority"].update(
        label="low", confidence=0.8, probs={"high": 0.1, "medium": 0.1, "low": 0.8},
    )

    def fail(*args, **kwargs):
        raise RuntimeError("Private provider error details.")

    monkeypatch.setattr(pipeline, "generate_draft", fail)
    result = agent.run("request-id", "Masked ticket text", mock["language"], mock["predictions"])

    assert result["draft"] is None
    assert result["escalation"]["route"] == "HUMAN_REVIEW"
    assert result["escalation"]["reasons"] == [{
        "code": "LLM_UNAVAILABLE",
        "message": "Draft generation is unavailable (Unexpected draft generation error).",
    }]


def test_figure_beyond_the_visible_resolution_escalates_a_previously_eligible_draft(monkeypatch, case):
    agent, mock = case
    mock["predictions"]["priority"].update(
        label="low", confidence=0.8, probs={"high": 0.1, "medium": 0.1, "low": 0.8},
    )
    mock["precedents"][0]["answer"] = "x" * pipeline.MAX_RESOLUTION_CHARS + " 50% Rabatt"
    draft = {**mock["draft"], "text": "Sie erhalten 50% Rabatt [TKT-00412].", "cited_ids": ["TKT-00412"]}

    def generate(text, reply_language, precedents, for_human_review):
        assert not for_human_review
        return draft

    monkeypatch.setattr(pipeline, "generate_draft", generate)
    result = agent.run("request-id", "Masked ticket text", mock["language"], mock["predictions"])
    assert result["draft"]["for_human_review"] is True
    assert result["escalation"]["route"] == "HUMAN_REVIEW"
    assert [reason["code"] for reason in result["escalation"]["reasons"]] == ["CITATION_CHECK_FAILED"]


def test_unsupported_request_still_gets_a_gemini_holding_reply(monkeypatch, case):
    _, mock = case
    mock["predictions"]["priority"].update(
        label="low", confidence=0.8, probs={"high": 0.1, "medium": 0.1, "low": 0.8},
    )
    retriever = SimpleNamespace(embed=lambda text: (1.0, 0.0), search=lambda vector, k: mock["precedents"])
    burst = SimpleNamespace(observe=lambda request_id, vector, summary: mock["burst"])
    holding = "Vielen Dank für Ihre Nachricht. Eine Fachkraft prüft Ihr Anliegen und meldet sich bei Ihnen."

    def generate(text, reply_language, precedents, for_human_review):
        assert for_human_review is True
        return {**mock["draft"], "status": "INSUFFICIENT_EVIDENCE", "text": holding, "cited_ids": []}

    monkeypatch.setattr(pipeline, "generate_draft", generate)
    agent = pipeline.AgentPipeline(retriever, burst)
    result = agent.run("request-id", "Ich möchte eine Rückerstattung.", mock["language"], mock["predictions"])

    assert [reason["code"] for reason in result["escalation"]["reasons"]] == [
        "UNSUPPORTED_REQUEST", "LLM_INSUFFICIENT_EVIDENCE",
    ]
    assert result["escalation"]["route"] == "HUMAN_REVIEW"
    assert result["draft"]["text"] == holding
    assert result["draft"]["model"] == mock["draft"]["model"]
    assert result["draft"]["for_human_review"] is True
