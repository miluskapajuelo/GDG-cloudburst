"""Run the hand-written demos through the B2 pipeline with offline stand-ins."""

import json
from pathlib import Path

from agent import config, pipeline
from shared.text import build_text


FIXTURES = Path(__file__).resolve().parents[1] / "shared" / "fixtures"


class FakeRetriever:
    def __init__(self, cases, default_precedents):
        self.cases = cases
        self.default_precedents = default_precedents

    def embed(self, text):
        return text

    def search(self, vector, k=5, exclude_ids=None):
        assert k == config.TOP_K
        return self.cases.get(vector, self.default_precedents)[:k]


class FakeBurstDetector:
    def __init__(self, burst_queries):
        self.burst_queries = burst_queries
        self.request_ids = []

    def observe(self, request_id, vector, summary):
        assert summary == vector[:120]
        cluster_ids = []
        if vector in self.burst_queries:
            self.request_ids.append(request_id)
            cluster_ids = self.request_ids
        active = len(cluster_ids) >= 3
        return {
            "active": active,
            "cluster_size": len(cluster_ids) or 1,
            "window_minutes": config.BURST_WINDOW_MIN,
            "label": "VPN timeouts" if active else None,
            "request_ids": cluster_ids.copy() if active else [],
        }


def _input_text(ticket):
    text = build_text(ticket["subject"], ticket["body"])
    if ticket["id"] == "demo-09":
        # B1 masks this text before the B2 entry point in the live service.
        for original, placeholder in {
            "jane.doe@example.com": "[EMAIL]",
            "+49 170 1234567": "[PHONE]",
            "88412093": "[ACCOUNT]",
            "192.168.14.22": "[IP]",
        }.items():
            text = text.replace(original, placeholder)
    return text


def _predictions(is_incident):
    ticket_type = "Incident" if is_incident else "Request"
    priority = "high" if is_incident else "low"
    return {
        "type": {
            "label": ticket_type,
            "confidence": 1.0,
            "probs": {"Incident": float(is_incident), "Request": float(not is_incident)},
        },
        "priority": {
            "label": priority,
            "confidence": 1.0,
            "probs": {"high": float(is_incident), "low": float(not is_incident)},
        },
        "queue": {"label": "Technical Support", "confidence": 1.0, "probs": {"Technical Support": 1.0}},
    }


def test_handwritten_demo_tickets_through_b2_pipeline(monkeypatch):
    """Exercise B2 wiring and policy, using supplied upstream model outputs."""
    tickets = json.loads((FIXTURES / "demo_tickets.json").read_text(encoding="utf-8"))["tickets"]
    mock = json.loads((FIXTURES / "mock_triage_response.json").read_text(encoding="utf-8"))
    text_by_id = {ticket["id"]: _input_text(ticket) for ticket in tickets}
    review_case = {
        **mock["precedents"][0],
        "ticket_id": "TKT-00001",
        "similarity": 0.90,
        "subject": "Support follow-up",
        "body_snippet": "How can I help support investigate?",
        "answer": "Please send your support reference number so we can investigate.",
        "answer_snippet": "Please send your support reference number so we can investigate.",
    }
    monkeypatch.setattr(config, "T_SIM", 0.55)
    retriever = FakeRetriever(
        {
            text_by_id["demo-01"]: mock["precedents"],
            text_by_id["demo-08"]: [{**review_case, "similarity": 0.10}],
        },
        [review_case],
    )
    burst = FakeBurstDetector({text_by_id[ticket["id"]] for ticket in tickets if ticket["burst"]})

    high_priority_incident_ids = {"demo-01", "demo-03", "demo-07", "demo-14"}
    blocked_ids = {"demo-07", "demo-08"}
    holding_ids = {"demo-03", "demo-04", "demo-14"}
    holding_texts = {text_by_id[ticket_id] for ticket_id in holding_ids}
    generator_calls = []

    def fake_generate_draft(text, reply_language, precedents, for_human_review):
        generator_calls.append(text)
        if text in holding_texts:
            # Gemini abstains on money, pricing and legal requests that no precedent supports.
            reply = (
                "Vielen Dank für Ihre Nachricht. Eine Fachkraft prüft Ihr Anliegen und meldet sich bei Ihnen."
                if reply_language == "de"
                else "Thank you for your message. A specialist will review your request and follow up."
            )
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "text": reply,
                "cited_ids": [],
                "language": reply_language,
                "for_human_review": for_human_review,
                "model": "offline-stub",
            }
        citation = precedents[0]["ticket_id"]
        if citation == "TKT-00412":
            reply = "Bitte prüfen Sie das Zertifikat des VPN-Gateways."
        elif reply_language == "de":
            reply = "Bitte nennen Sie uns Ihre Vorgangsnummer."
        else:
            reply = "Please send us your support reference number."
        return {
            "status": "OK",
            "text": f"{reply} [{citation}]",
            "cited_ids": [citation],
            "language": reply_language,
            "for_human_review": for_human_review,
            "model": "offline-stub",
        }

    monkeypatch.setattr(pipeline, "generate_draft", fake_generate_draft)
    agent = pipeline.AgentPipeline(retriever, burst)
    for ticket in tickets:
        ticket_id = ticket["id"]
        text = text_by_id[ticket_id]
        code = ticket["expected_reply_language"]
        language = {"code": code, "confidence": 1.0, "reply_language": code}
        result = agent.run(ticket_id, text, language, _predictions(ticket_id in high_priority_incident_ids))
        escalation = result["escalation"]
        draft = result["draft"]
        expected_codes = set(ticket["expected_reason_codes_any"])
        reason_codes = {reason["code"] for reason in escalation["reasons"]}

        if ticket["expected_status"] is not None:
            assert escalation["status"] == ticket["expected_status"], ticket_id
            assert escalation["route"] == ticket["expected_route"], ticket_id
        if expected_codes:
            assert not reason_codes.isdisjoint(expected_codes), (ticket_id, reason_codes)

        if ticket_id in blocked_ids:
            assert text not in generator_calls, ticket_id
            assert draft is None, ticket_id
            assert result["latency_ms"]["generate"] == 0, ticket_id
        elif ticket_id in holding_ids:
            assert text in generator_calls, ticket_id
            assert draft["status"] == "INSUFFICIENT_EVIDENCE", ticket_id
            assert {"UNSUPPORTED_REQUEST", "LLM_INSUFFICIENT_EVIDENCE"} <= reason_codes, (ticket_id, reason_codes)
            assert draft["cited_ids"] == [], ticket_id
            assert all(claim not in draft["text"] for claim in ("20%", "$", "€", "SAP S/4HANA")), ticket_id
        else:
            assert text in generator_calls, ticket_id
            assert draft["status"] == "OK", ticket_id
            assert draft["cited_ids"] == [result["precedents"][0]["ticket_id"]], ticket_id

        if draft is not None:
            assert draft["language"] == code, ticket_id
            assert draft["for_human_review"] == (escalation["status"] == "ESCALATE"), ticket_id
        if ticket_id in {"demo-01", "demo-15"}:
            assert result["precedents"][0]["language"] == "en", ticket_id
            assert draft["language"] == "de", ticket_id
        if ticket["burst"]:
            assert result["burst"]["active"] == ticket.get("expected_burst_active", False), ticket_id

