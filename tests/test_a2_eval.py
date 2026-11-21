"""A2.3 tests: eval/run_eval.py on tiny synthetic data with a fake triage function.

Never touches the real data/ folder or the real test labels.
Run: python -m pytest tests/test_a2_eval.py -q
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eval import run_eval as ev

# ---------------------------------------------------------------- synthetic data

TEST_ROWS = [
    # ticket_id, subject, body, true type, queue, priority, language
    ("TKT-00009", "VPN down", "outage everywhere, urgent", "Incident", "Technical Support", "high", "en"),
    ("TKT-00007", "", "Drucker Ausfall dringend outage", "Incident", "IT Support", "high", "de"),
    ("TKT-00008", "Invoice", "please send invoice copy", "Request", "Billing and Payments", "low", "en"),
    ("TKT-00006", "Frage", "wie aendere ich mein Passwort", "Request", "Customer Service", "medium", "de"),
    ("TKT-00005", "Login", "login broken since update", "Problem", "Technical Support", "high", "en"),
]


def write_dataset(ddir: Path, *, answer_in_inputs: bool = False, overlap: bool = False,
                  answer_in_labels: bool = False) -> None:
    ddir.mkdir(parents=True, exist_ok=True)
    kb_ids = [f"TKT-0000{i}" for i in range(5)]
    if overlap:
        kb_ids[0] = TEST_ROWS[0][0]
    kb = pd.DataFrame({
        "ticket_id": kb_ids, "subject": "s", "body": "b", "answer": "kb answer",
        "type": "Incident", "queue": "IT Support", "priority": "high", "language": "en",
        "is_val": [False, False, False, True, False],
    })
    kb.to_parquet(ddir / "kb_train.parquet", index=False)
    inputs = pd.DataFrame([r[:3] for r in TEST_ROWS], columns=["ticket_id", "subject", "body"])
    if answer_in_inputs:
        inputs["answer"] = "leaked"
    inputs.to_parquet(ddir / "test_inputs.parquet", index=False)
    labels = pd.DataFrame([(r[0], *r[3:]) for r in TEST_ROWS],
                          columns=["ticket_id", "type", "queue", "priority", "language"])
    if answer_in_labels:
        labels["answer"] = "leaked"
    labels.to_parquet(ddir / "test_labels.parquet", index=False)


def _pred(label: str, labels: list[str]) -> dict:
    rest = (1.0 - 0.7) / (len(labels) - 1)
    probs = {lab: (0.7 if lab == label else rest) for lab in labels}
    return {"label": label, "confidence": 0.7, "probs": probs}


def fake_triage(subject: str | None, body: str, *, skip_llm: bool = False) -> dict:
    """Contract-shaped response. 'outage' -> high Incident escalated ON_CALL; 'login' -> HUMAN_REVIEW
    with two reasons; anything else -> AUTO_DRAFT. German if 'Drucker' or 'wie' appears."""
    assert skip_llm is True
    text = f"{subject or ''} {body}".lower()
    if "outage" in text:
        t, q, p = "Incident", "Technical Support", "high"
        reasons = [{"code": "HIGH_PRIORITY_INCIDENT", "message": "m"}, {"code": "NO_PRECEDENT", "message": "m"}]
        status, route = "ESCALATE", "ON_CALL"
    elif "login" in text:
        t, q, p = "Incident", "Technical Support", "medium"
        reasons = [{"code": "LOW_CLASSIFIER_CONFIDENCE", "message": "m"}, {"code": "NO_PRECEDENT", "message": "m"}]
        status, route = "ESCALATE", "HUMAN_REVIEW"
    else:
        t, q, p = "Request", "Customer Service", "low"
        reasons, status, route = [], "AUTO_DRAFT", None
    code = "de" if ("drucker" in text or "wie " in text) else "en"
    return {
        "request_id": "r",
        "mock": False,
        "input": {"subject": subject, "body_chars": len(body), "truncated": False},
        "language": {"code": code, "confidence": 0.9, "reply_language": code},
        "pii": {"masked": False, "counts": {k: 0 for k in ("EMAIL", "PHONE", "IP", "IBAN", "CARD", "ACCOUNT")}},
        "predictions": {
            "type": _pred(t, ["Incident", "Request", "Problem", "Change"]),
            "queue": _pred(q, ["Technical Support", "Customer Service", "IT Support", "Billing and Payments"]),
            "priority": _pred(p, ["high", "medium", "low"]),
        },
        "escalation": {"status": status, "route": route, "badge": "b", "reasons": reasons},
        "precedents": [],
        "draft": None,
        "burst": {"active": False, "cluster_size": 1, "window_minutes": 15, "label": None, "request_ids": []},
        "latency_ms": {"pii": 1, "language": 2, "classify": 9, "retrieve": 25, "gate": 1, "generate": 0, "total": 40},
    }


A26_SHAPE = {
    "generated_at": None, "split_fingerprint": None, "n_test": None,
    "classifier": {h: {"macro_f1": None, "weighted_f1": None, "accuracy": None} for h in ("type", "queue", "priority")},
    "high_priority_incident": {"support": None, "classifier_recall": None, "escalation_recall": None},
    "escalation": {"rate": None, "reason_counts": None},
    "language_detection_accuracy": None,
    "latency_ms": {
        "skip_llm": {"p50": None, "p95": None, "n": None},
        "with_llm": {"p50": None, "p95": None, "generate_p50": None, "generate_p95": None, "n": None},
    },
    "grounding": {"n": None, "citation_valid_rate": None, "draft_with_citation_rate": None,
                  "insufficient_evidence_rate": None, "llm_unavailable_rate": None, "reply_language_match_rate": None},
    "thresholds": None,
}
ALLOWED_EXTRA = {("latency_ms", "skip_llm_stages")}


def assert_shape(actual: dict, expected: dict, path: tuple = ()) -> None:
    extra = {k for k in set(actual) - set(expected) if path + (k,) not in ALLOWED_EXTRA}
    assert set(expected) <= set(actual), f"missing at {path}: {set(expected) - set(actual)}"
    assert not extra, f"unexpected keys at {path}: {extra}"
    for k, sub in expected.items():
        if isinstance(sub, dict):
            assert isinstance(actual[k], dict), f"{path + (k,)} must be an object"
            assert_shape(actual[k], sub, path + (k,))


def assert_plain(obj, path="") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert isinstance(k, str)
            assert_plain(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_plain(v, f"{path}[{i}]")
    else:
        assert not isinstance(obj, np.generic), f"numpy type at {path}: {type(obj)}"
        assert obj is None or type(obj) in (str, int, float, bool), f"non-plain type at {path}: {type(obj)}"


def run_synthetic(tmp_path: Path, triage=fake_triage, **kw) -> dict:
    ddir = tmp_path / "data"
    write_dataset(ddir)
    kb, inputs = ev.load_inputs(ddir)
    fp = ev.check_leakage(kb, inputs)
    return ev.run_eval(inputs, triage, ddir=ddir, out_dir=tmp_path / "out", fingerprint=fp,
                       thresholds={"T_SIM": np.float64(0.55), "TOP_K": np.int64(5)}, progress_every=2, **kw)


# ---------------------------------------------------------------- fingerprint and leakage asserts

def test_fingerprint_formula_file_order_comma_joined():
    ids = pd.Series(["TKT-00009", "TKT-00007", "TKT-00008"])
    expected = hashlib.sha256(b"TKT-00009,TKT-00007,TKT-00008").hexdigest()[:12]
    assert ev.split_fingerprint(ids) == expected
    assert ev.split_fingerprint(sorted(ids)) != expected  # order matters: not sorted
    from ml.make_split import fingerprint as split_side
    assert ev.split_fingerprint(ids) == split_side(ids)


def test_fingerprint_uses_full_inputs_before_limit(tmp_path, capsys):
    metrics = run_synthetic(tmp_path, limit=2)
    full = ev.split_fingerprint([r[0] for r in TEST_ROWS])
    assert metrics["split_fingerprint"] == full
    assert metrics["n_test"] == 2
    assert full in capsys.readouterr().out


def test_leakage_assert_answer_in_inputs(tmp_path):
    write_dataset(tmp_path, answer_in_inputs=True)
    kb, inputs = ev.load_inputs(tmp_path)
    with pytest.raises(AssertionError, match="answer"):
        ev.check_leakage(kb, inputs)


def test_leakage_assert_overlapping_ids(tmp_path):
    write_dataset(tmp_path, overlap=True)
    kb, inputs = ev.load_inputs(tmp_path)
    with pytest.raises(AssertionError, match="overlap"):
        ev.check_leakage(kb, inputs)


def test_leakage_assert_answer_in_labels(tmp_path):
    write_dataset(tmp_path, answer_in_labels=True)
    with pytest.raises(AssertionError, match="answer"):
        ev.load_labels(tmp_path)


def test_check_leakage_prints_row_counts(tmp_path, capsys):
    write_dataset(tmp_path)
    ev.check_leakage(*ev.load_inputs(tmp_path))
    out = capsys.readouterr().out
    assert "kb=5 (fit=4, val=1)  test=5" in out


# ---------------------------------------------------------------- ordering: predictions before labels

def test_predictions_written_before_labels_are_read(tmp_path, monkeypatch):
    calls = []
    real_loader = ev.load_labels

    def spy(ddir):
        pred_path = tmp_path / "out" / "test_predictions.parquet"
        assert pred_path.exists(), "labels were read before predictions were saved"
        assert len(pd.read_parquet(pred_path)) == len(TEST_ROWS)
        calls.append(ddir)
        return real_loader(ddir)

    def triage_guard(subject, body, *, skip_llm=False):
        assert not calls, "labels were read during prediction"
        return fake_triage(subject, body, skip_llm=skip_llm)

    monkeypatch.setattr(ev, "load_labels", spy)
    run_synthetic(tmp_path, triage=triage_guard)
    assert len(calls) == 1


def test_inputs_loading_never_touches_labels(tmp_path, monkeypatch):
    write_dataset(tmp_path)
    real_read = pd.read_parquet

    def guarded(path, *a, **kw):
        assert "test_labels" not in str(path)
        return real_read(path, *a, **kw)

    monkeypatch.setattr(pd, "read_parquet", guarded)
    ev.check_leakage(*ev.load_inputs(tmp_path))


def test_predictions_file_contents(tmp_path):
    run_synthetic(tmp_path)
    preds = pd.read_parquet(tmp_path / "out" / "test_predictions.parquet")
    for col in ("ticket_id", "type_label", "type_conf", "queue_label", "queue_conf", "priority_label",
                "priority_conf", "status", "route", "reason_codes", "lang_code", "lat_pii", "lat_language",
                "lat_classify", "lat_retrieve", "lat_gate", "lat_total"):
        assert col in preds.columns
    # no ground-truth columns in the predictions file
    assert not {"type", "queue", "priority", "language", "answer"} & set(preds.columns)
    assert list(preds["ticket_id"]) == [r[0] for r in TEST_ROWS]
    first = preds.iloc[0]
    assert first["reason_codes"] == "HIGH_PRIORITY_INCIDENT|NO_PRECEDENT"
    assert first["lat_total"] == 40 and isinstance(first["lat_total"], (int, np.integer))


# ---------------------------------------------------------------- metrics shape

def test_metrics_json_matches_a26_shape(tmp_path):
    returned = run_synthetic(tmp_path)
    on_disk = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
    for m in (returned, on_disk):
        assert_shape(m, A26_SHAPE)
    assert_plain(returned)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", on_disk["generated_at"])
    assert on_disk["n_test"] == len(TEST_ROWS)
    assert on_disk["thresholds"] == {"T_SIM": 0.55, "TOP_K": 5}
    assert on_disk["latency_ms"]["skip_llm"] == {"p50": 40, "p95": 40, "n": 5}
    assert on_disk["latency_ms"]["with_llm"]["n"] == 0 and on_disk["grounding"]["n"] == 0
    assert on_disk["latency_ms"]["skip_llm_stages"]["retrieve"] == {"p50": 25, "p95": 25}

    md = (tmp_path / "out" / "metrics.md").read_text(encoding="utf-8")
    for needle in ("Confusion matrix: queue", "Per-class report: priority", "Triage errors: 0",
                   "retrieve", "label is noisy", on_disk["split_fingerprint"]):
        assert needle in md
    assert md.isascii()


# ---------------------------------------------------------------- scoring math

def _preds_frame(rows):
    cols = ["ticket_id", "type_label", "priority_label", "queue_label", "status", "route", "reason_codes", "lang_code"]
    df = pd.DataFrame(rows, columns=cols)
    for head in ("type", "queue", "priority"):
        df[f"{head}_conf"] = 0.9
    for s in ev.STAGES:
        df[f"lat_{s}"] = 10
    df["wall_ms"] = 11
    df["error"] = None
    return df


def _labels_frame(rows):
    return pd.DataFrame(rows, columns=["ticket_id", "type", "priority", "queue", "language"])


def test_hpi_recall_hand_computed():
    q = "IT Support"
    preds = _preds_frame([
        # 4 true HPI tickets:
        ("A", "Incident", "high", q, "ESCALATE", "ON_CALL", "HIGH_PRIORITY_INCIDENT", "en"),   # clf hit, escalated
        ("B", "Problem", "high", q, "ESCALATE", "HUMAN_REVIEW", "NO_PRECEDENT", "en"),        # clf miss, escalated
        ("C", "Incident", "medium", q, "ESCALATE", "HUMAN_REVIEW", "LOW_CLASSIFIER_CONFIDENCE", "en"),  # miss, esc
        ("D", "Incident", "high", q, "AUTO_DRAFT", None, "", "en"),                             # clf hit, not esc
        # non-HPI tickets predicted as HPI must not change recall:
        ("E", "Incident", "high", q, "ESCALATE", "ON_CALL", "HIGH_PRIORITY_INCIDENT", "en"),
        ("F", "Request", "low", q, "AUTO_DRAFT", None, "", "en"),
    ])
    labels = _labels_frame([
        ("A", "Incident", "high", q, "en"), ("B", "Incident", "high", q, "en"),
        ("C", "Incident", "high", q, "en"), ("D", "Incident", "high", q, "en"),
        ("E", "Request", "high", q, "en"), ("F", "Incident", "medium", q, "en"),
    ])
    s = ev.score(preds, labels)
    assert s["high_priority_incident"] == {"support": 4, "classifier_recall": 0.5, "escalation_recall": 0.75}
    assert s["hpi_routes"] == {"ESCALATE / HUMAN_REVIEW": 2, "ESCALATE / ON_CALL": 1, "AUTO_DRAFT": 1}
    assert s["escalation"]["rate"] == round(4 / 6, 4)


def test_reason_counts_count_every_reason():
    q = "IT Support"
    preds = _preds_frame([
        ("A", "Incident", "high", q, "ESCALATE", "ON_CALL", "HIGH_PRIORITY_INCIDENT|NO_PRECEDENT|UNSUPPORTED_REQUEST", "en"),
        ("B", "Request", "low", q, "ESCALATE", "HUMAN_REVIEW", "NO_PRECEDENT", "en"),
        ("C", "Request", "low", q, "AUTO_DRAFT", None, "", "en"),
    ])
    labels = _labels_frame([("A", "Incident", "high", q, "en"), ("B", "Request", "low", q, "en"),
                            ("C", "Request", "low", q, "de")])
    s = ev.score(preds, labels)
    rc = s["escalation"]["reason_counts"]
    assert rc["HIGH_PRIORITY_INCIDENT"] == 1 and rc["NO_PRECEDENT"] == 2 and rc["UNSUPPORTED_REQUEST"] == 1
    assert rc["PROMPT_INJECTION_SUSPECTED"] == 0 and rc["LOW_CLASSIFIER_CONFIDENCE"] == 0
    assert s["escalation"]["rate"] == round(2 / 3, 4)
    assert s["language_detection_accuracy"] == round(2 / 3, 4)
    assert s["language_detail"]["de"] == {"n": 1, "accuracy": 0.0, "detected": {"en": 1}}


def test_classifier_metrics_use_label_union():
    q = "IT Support"
    preds = _preds_frame([
        ("A", "Incident", "high", q, "AUTO_DRAFT", None, "", "en"),
        ("B", "Change", "high", q, "AUTO_DRAFT", None, "", "en"),  # "Change" never appears in the truth
    ])
    labels = _labels_frame([("A", "Incident", "high", q, "en"), ("B", "Incident", "high", q, "en")])
    s = ev.score(preds, labels)
    t = s["heads"]["type"]
    assert t["confusion"]["rows"] == ["Change", "Incident"]
    assert t["confusion"]["matrix"] == [[0, 0], [1, 1]]
    assert t["accuracy"] == 0.5
    # F1(Incident) = 2*1*0.5/1.5 = 0.6667, F1(Change) = 0 -> macro 0.3333
    assert t["macro_f1"] == round(1 / 3, 4)


# ---------------------------------------------------------------- robustness and CLI

def test_triage_error_does_not_crash(tmp_path):
    def flaky(subject, body, *, skip_llm=False):
        if "invoice" in body:
            raise RuntimeError("boom")
        return fake_triage(subject, body, skip_llm=skip_llm)

    metrics = run_synthetic(tmp_path, triage=flaky)
    preds = pd.read_parquet(tmp_path / "out" / "test_predictions.parquet")
    assert (preds["status"] == ev.ERROR_STATUS).sum() == 1
    assert preds.loc[preds["status"] == ev.ERROR_STATUS, "error"].iloc[0] == "RuntimeError: boom"
    assert metrics["latency_ms"]["skip_llm"]["n"] == 4
    assert metrics["classifier"]["type"]["accuracy"] <= 0.8  # the error row counts as wrong
    md = (tmp_path / "out" / "metrics.md").read_text(encoding="utf-8")
    assert "Triage errors: 1" in md and "RuntimeError" in md


def test_main_check_only_does_not_import_service(tmp_path, monkeypatch, capsys):
    write_dataset(tmp_path)
    (tmp_path / "test_labels.parquet").unlink()  # --check-only must not need the labels
    monkeypatch.setenv("SENTINEL_DATA_DIR", str(tmp_path))
    monkeypatch.delitem(sys.modules, "api.service", raising=False)
    assert ev.main(["--check-only"]) == 0
    assert "api.service" not in sys.modules
    out = capsys.readouterr().out
    assert ev.split_fingerprint([r[0] for r in TEST_ROWS]) in out
    assert out.isascii()


def test_main_with_fake_service(tmp_path, monkeypatch, capsys):
    ddir = tmp_path / "data"
    write_dataset(ddir)
    fake = types.ModuleType("api.service")
    fake.started = False

    def startup():
        fake.started = True

    fake.startup = startup
    fake.get_config = lambda: {"T_SIM": 0.6}
    fake.triage = fake_triage
    monkeypatch.setitem(sys.modules, "api.service", fake)
    monkeypatch.setenv("SENTINEL_DATA_DIR", str(ddir))

    out_dir = tmp_path / "res"
    assert ev.main(["--out", str(out_dir), "--llm-sample", "5", "--limit", "3"]) == 0
    assert fake.started
    metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["thresholds"] == {"T_SIM": 0.6} and metrics["n_test"] == 3
    out = capsys.readouterr().out
    assert "A2.5" in out and "not implemented" in out
    assert out.isascii()
