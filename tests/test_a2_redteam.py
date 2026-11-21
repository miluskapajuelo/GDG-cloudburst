"""A2.8 tests: eval/run_redteam.py with fake triage functions. No models, no network.

Run: python -m pytest tests/test_a2_redteam.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import run_redteam as rt

FIXTURE = Path(__file__).resolve().parents[1] / "shared" / "fixtures" / "demo_tickets.json"


def resp(status="AUTO_DRAFT", route=None, codes=(), reply="en", draft="auto", precedents=("TKT-00001",),
         pii=None, burst=False):
    if draft == "auto":
        draft = {"status": "OK", "text": "Hello [TKT-00001]", "cited_ids": ["TKT-00001"], "language": reply,
                 "for_human_review": status == "ESCALATE", "model": "m"}
    return {
        "escalation": {"status": status, "route": route, "badge": "b",
                       "reasons": [{"code": c, "message": "m"} for c in codes]},
        "language": {"code": reply, "confidence": 0.9, "reply_language": reply},
        "pii": {"masked": bool(pii), "counts": pii or {}},
        "precedents": [{"ticket_id": p} for p in precedents],
        "draft": draft,
        "burst": {"active": burst},
        "latency_ms": {"total": 10},
    }


def T(**kw):
    base = {"id": "t", "title": "t", "subject": "", "body": "b", "burst": False, "expected_status": None,
            "expected_route": None, "expected_reason_codes_any": [], "expected_reply_language": "en"}
    return {**base, **kw}


def test_pass_when_everything_matches():
    t = T(expected_status="ESCALATE", expected_route="ON_CALL", expected_reason_codes_any=["HIGH_PRIORITY_INCIDENT"])
    assert rt.check(t, resp("ESCALATE", "ON_CALL", ["HIGH_PRIORITY_INCIDENT"]), skip_llm=False) == []


def test_null_status_accepts_either_outcome():
    assert rt.check(T(), resp("AUTO_DRAFT"), skip_llm=False) == []
    assert rt.check(T(), resp("ESCALATE", "HUMAN_REVIEW", ["NO_PRECEDENT"], draft=None), skip_llm=False) == []


def test_status_route_and_codes_failures():
    t = T(expected_status="ESCALATE", expected_route="HUMAN_REVIEW",
          expected_reason_codes_any=["UNSUPPORTED_REQUEST", "LLM_INSUFFICIENT_EVIDENCE"])
    f = rt.check(t, resp("AUTO_DRAFT"), skip_llm=False)
    assert any("status AUTO_DRAFT" in x for x in f) and any("reason codes" in x for x in f)
    f = rt.check(t, resp("ESCALATE", "ON_CALL", ["HIGH_PRIORITY_INCIDENT", "UNSUPPORTED_REQUEST"]), skip_llm=False)
    assert f == ["route ON_CALL (expected HUMAN_REVIEW)"]
    t2 = T(expected_status="AUTO_DRAFT", expected_route=None)
    assert rt.check(t2, resp("AUTO_DRAFT"), skip_llm=False) == []


def test_reply_language_pii_and_burst():
    t = T(expected_reply_language="de", expected_pii_counts={"EMAIL": 1, "PHONE": 1}, expected_burst_active=True)
    f = rt.check(t, resp(reply="en", pii={"EMAIL": 1, "PHONE": 0}, burst=False), skip_llm=False)
    assert any("reply_language en" in x for x in f)
    assert any("pii counts {'PHONE': 0}" in x for x in f)
    assert any("burst.active False" in x for x in f)
    ok = rt.check(t, resp(reply="de", pii={"EMAIL": 1, "PHONE": 1, "IP": 3}, burst=True), skip_llm=False)
    assert ok == []


def test_draft_safety_checks():
    inj = resp("ESCALATE", "HUMAN_REVIEW", ["PROMPT_INJECTION_SUSPECTED"])
    assert any("despite ['PROMPT_INJECTION_SUSPECTED']" in x for x in rt.check(T(), inj, skip_llm=False))
    stray = resp()
    stray["draft"]["cited_ids"] = ["TKT-99999"]
    assert any("TKT-99999" in x for x in rt.check(T(), stray, skip_llm=False))
    wrong_lang = resp(reply="en")
    wrong_lang["draft"]["language"] = "de"
    assert any("draft.language de" in x for x in rt.check(T(), wrong_lang, skip_llm=False))
    review = resp("ESCALATE", "HUMAN_REVIEW", ["LOW_CLASSIFIER_CONFIDENCE"])
    review["draft"]["for_human_review"] = False
    assert any("for_human_review" in x for x in rt.check(T(), review, skip_llm=False))


def test_skip_llm_requires_null_draft_and_skips_draft_checks():
    assert rt.check(T(), resp(draft=None), skip_llm=True) == []
    assert any("skip_llm" in x for x in rt.check(T(), resp(), skip_llm=True))


def test_run_order_resets_and_errors():
    tickets = [T(id="a"), T(id="b", burst=True), T(id="c", burst=True), T(id="d", body="boom")]
    log = []

    def triage(subject, body, skip_llm):
        log.append(("triage", body))
        if body == "boom":
            raise RuntimeError("down")
        return resp()

    results = rt.run(tickets, triage, lambda: log.append(("reset",)))
    assert log == [("reset",), ("triage", "b"), ("reset",), ("triage", "b"), ("triage", "b"), ("triage", "boom")]
    assert [r["id"] for r in results] == ["a", "b", "c", "d"]
    assert [r["passed"] for r in results] == [True, True, True, False]
    assert "RuntimeError" in results[3]["failures"][0]


def test_report_has_table_and_failure_drafts(tmp_path):
    tickets = [T(id="ok"), T(id="bad", expected_status="ESCALATE", expected_route="HUMAN_REVIEW")]
    results = rt.run(tickets, lambda s, b, k: resp(), lambda: None)
    md = rt.render_md(results, mode="test", health={"mock": False}, skip_llm=False)
    assert "**Passed: 1/2**" in md and "## Failures: draft text" in md and "Hello [TKT-00001]" in md
    rt.write_outputs(results, md, tmp_path)
    assert json.loads((tmp_path / "redteam.json").read_text(encoding="utf-8"))[1]["passed"] is False


def test_real_fixture_loads_and_burst_tickets_are_consecutive():
    tickets = rt.load_tickets(FIXTURE)
    assert len(tickets) >= 15
    flags = [bool(t.get("burst")) for t in tickets]
    first, last = flags.index(True), len(flags) - 1 - flags[::-1].index(True)
    assert all(flags[first:last + 1]), "burst tickets must be consecutive in the fixture"
    # every ticket passes a perfectly matching fake response
    for t in tickets:
        status = t["expected_status"] or "AUTO_DRAFT"
        codes = (t["expected_reason_codes_any"] or [])[:1]
        no_draft = any(c in rt.NO_DRAFT_CODES for c in codes)
        r = resp(status, t["expected_route"] if t["expected_status"] else None, codes,
                 reply=t["expected_reply_language"], draft=None if no_draft else "auto",
                 pii=t.get("expected_pii_counts"), burst=bool(t.get("expected_burst_active")))
        assert rt.check(t, r, skip_llm=False) == [], t["id"]


def test_main_with_fake_service(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(rt, "in_process", lambda: (lambda s, b, k: (calls.append(k), resp())[1],
                                                   lambda: None, {"mock": False}))
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    assert rt.main(["--out", str(tmp_path), "--skip-llm"]) == 0
    assert calls and all(calls)  # skip_llm passed through
    assert rt.main(["--out", str(tmp_path), "--strict"]) == 1  # fake responses cannot satisfy every ticket
