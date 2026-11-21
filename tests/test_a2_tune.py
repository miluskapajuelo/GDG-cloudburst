"""A2.7 tests: eval/tune_thresholds.py on synthetic val data. No real data, index or network.

Run: python -m pytest tests/test_a2_tune.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eval import tune_thresholds as tt


def _feats(rows):
    cols = ["ticket_id", "type", "priority", "p_high", "p_incident", "conf_type", "conf_priority", "conf_queue",
            "top1_sim", "injection", "unsupported"]
    df = pd.DataFrame(rows, columns=cols)
    df["true_hpi"] = (df["priority"] == "high") & (df["type"] == "Incident")
    return df


BASE = dict(T_HIGH_PRIORITY_P=0.35, T_INCIDENT_P=0.40, T_CONF_TYPE=0.45, T_CONF_PRIORITY=0.45,
            T_CONF_QUEUE=0.25, T_SIM=0.55)


def test_evaluate_hand_computed():
    f = _feats([
        # true HPI, caught by rule 2
        ("A", "Incident", "high", 0.6, 0.7, 0.8, 0.8, 0.5, 0.9, False, False),
        # true HPI, rule 2 misses (p_high low) but NO_PRECEDENT escalates it
        ("B", "Incident", "high", 0.2, 0.7, 0.8, 0.8, 0.5, 0.4, False, False),
        # true HPI, nothing fires
        ("C", "Incident", "high", 0.2, 0.7, 0.8, 0.8, 0.5, 0.9, False, False),
        # not HPI, low queue confidence
        ("D", "Request", "low", 0.1, 0.1, 0.8, 0.8, 0.1, 0.9, False, False),
        # not HPI, unsupported request (threshold-free)
        ("E", "Request", "low", 0.1, 0.1, 0.8, 0.8, 0.5, 0.9, False, True),
        # not HPI, clean -> AUTO_DRAFT
        ("F", "Request", "low", 0.1, 0.1, 0.8, 0.8, 0.5, 0.9, False, False),
    ])
    r = tt.evaluate(f, BASE)
    assert r["hpi_escalation_recall"] == pytest.approx(2 / 3)
    assert r["hpi_on_call_recall"] == pytest.approx(1 / 3)
    assert r["escalation_rate"] == pytest.approx(4 / 6)
    assert r["no_precedent_rate"] == pytest.approx(1 / 6)
    assert r["low_conf_rate"] == pytest.approx(1 / 6)
    assert r["on_call_rate"] == pytest.approx(1 / 6)


def test_thresholds_use_ge_for_rule2_and_lt_for_sim():
    f = _feats([("A", "Incident", "high", 0.35, 0.40, 0.45, 0.45, 0.25, 0.55, False, False)])
    r = tt.evaluate(f, BASE)
    assert r["on_call_rate"] == 1.0          # p >= threshold fires
    assert r["no_precedent_rate"] == 0.0     # sim == T_SIM is not below
    assert r["low_conf_rate"] == 0.0         # conf == threshold is not below


def _synthetic(n=400, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        hpi = i % 5 == 0
        rows.append((f"TKT-{i:05d}", "Incident" if hpi else "Request", "high" if hpi else "low",
                     float(rng.uniform(0.3, 0.9) if hpi else rng.uniform(0.0, 0.4)),
                     float(rng.uniform(0.4, 0.9) if hpi else rng.uniform(0.0, 0.5)),
                     float(rng.uniform(0.3, 0.95)), float(rng.uniform(0.3, 0.95)), float(rng.uniform(0.1, 0.8)),
                     float(rng.uniform(0.45, 0.95)), False, bool(i % 37 == 0)))
    return _feats(rows)


def test_sweep_covers_grid_and_sim_percentiles():
    f = _synthetic()
    res = tt.sweep(f)
    sims = tt.sim_candidates(f["top1_sim"])
    n_expected = 7 * 7 * 4 * 4 * len(sims)
    assert len(res) == n_expected
    p5 = round(float(np.percentile(f["top1_sim"], 5)), 3)
    assert p5 in set(res["T_SIM"].round(3))
    assert (res["T_CONF_TYPE"] == res["T_CONF_PRIORITY"]).all()


def test_recommend_meets_targets_when_possible():
    f = _synthetic()
    res = tt.sweep(f)
    best, note = tt.recommend(res)
    ok = res[(res["hpi_escalation_recall"] >= 0.9) & res["escalation_rate"].between(0.3, 0.5)
             & (res["no_precedent_rate"] < 0.1)]
    if len(ok):
        assert note == "all three targets met"
        assert best["hpi_escalation_recall"] >= 0.9 and 0.3 <= best["escalation_rate"] <= 0.5
        assert best["no_precedent_rate"] < 0.1
        assert best["hpi_escalation_recall"] == pytest.approx(ok["hpi_escalation_recall"].max(), abs=1e-4)
        top = ok[np.isclose(ok["hpi_escalation_recall"], ok["hpi_escalation_recall"].max(), atol=1e-4)]
        assert best["escalation_rate"] == pytest.approx(top["escalation_rate"].min(), abs=1e-4)
    else:
        assert note != "all three targets met"


def test_recommend_relaxes_in_priority_order():
    res = pd.DataFrame([
        # meets recall + rate, fails NO_PRECEDENT
        dict(BASE, hpi_escalation_recall=0.95, escalation_rate=0.40, no_precedent_rate=0.20),
        # meets recall only, low rate
        dict(BASE, hpi_escalation_recall=0.99, escalation_rate=0.20, no_precedent_rate=0.05),
        # fails recall
        dict(BASE, hpi_escalation_recall=0.50, escalation_rate=0.35, no_precedent_rate=0.01),
    ])
    best, note = tt.recommend(res)
    assert best["no_precedent_rate"] == 0.20 and "NO_PRECEDENT target relaxed" in note

    best, note = tt.recommend(res.iloc[[1, 2]])  # only recall can be met: the 0.99 / rate 0.20 row
    assert best["hpi_escalation_recall"] == 0.99 and "escalation-rate" in note

    best, note = tt.recommend(res.iloc[[2]])
    assert "no setting reaches" in note and best["hpi_escalation_recall"] == 0.50


def test_classifier_features_from_val_preds_columns():
    probs = pd.DataFrame({
        "ticket_id": ["A", "B"],
        "type__Incident": [0.7, 0.1], "type__Request": [0.3, 0.9],
        "priority__high": [0.6, 0.2], "priority__low": [0.4, 0.8],
        "queue__IT": [0.5, 0.3], "queue__Billing": [0.5, 0.7],
    })
    f = tt.classifier_features(probs)
    assert list(f["p_high"]) == [0.6, 0.2] and list(f["p_incident"]) == [0.7, 0.1]
    assert list(f["conf_type"]) == [0.7, 0.9] and list(f["conf_queue"]) == [0.5, 0.7]
    preds = tt.predictions_from_row(probs.iloc[1], {h: [c for c in probs if c.startswith(h + "__")]
                                                    for h in tt.HEADS})
    assert preds["type"] == {"label": "Request", "confidence": 0.9, "probs": {"Incident": 0.1, "Request": 0.9}}


def test_retrieval_features_excludes_self_and_uses_gate():
    val = pd.DataFrame({"ticket_id": ["A", "B"], "subject": ["s", None], "body": ["refund please", "vpn down"],
                        "type": ["Request", "Incident"], "priority": ["low", "high"]})
    probs = pd.DataFrame({"ticket_id": ["A", "B"], "type__Incident": [0.1, 0.8], "type__Request": [0.9, 0.2],
                          "priority__high": [0.1, 0.7], "priority__low": [0.9, 0.3],
                          "queue__IT": [0.6, 0.6], "queue__Billing": [0.4, 0.4]})
    seen = []

    def embed_search(text, tid):
        seen.append((text, tid))
        return [{"ticket_id": "KB-1", "similarity": 0.8 if tid == "A" else 0.3, "answer": "reset done"}]

    def gate(preds, precedents, text):
        reasons = [{"code": "UNSUPPORTED_REQUEST", "message": "m"}] if "refund" in text else []
        assert preds["type"]["label"] in ("Request", "Incident")
        return {"reasons": reasons, "allow_draft": True}

    ret = tt.retrieval_features(val, probs, embed_search=embed_search, mask_pii=lambda t: (t.upper(), {}),
                                build_text=lambda s, b: f"{s or ''} {b}".strip(), pre_draft_gate=gate)
    assert [t for _, t in seen] == ["A", "B"]                  # exclude_ids = own ticket id
    assert seen[0][0] == "S REFUND PLEASE"                     # masked text is what gets embedded
    assert list(ret["top1_sim"]) == [0.8, 0.3]
    assert list(ret["unsupported"]) == [False, False]          # gate sees masked (upper-case) text here
    assert list(ret["injection"]) == [False, False]

    def bad_search(text, tid):
        return [{"ticket_id": tid, "similarity": 1.0}]

    with pytest.raises(AssertionError, match="self-match"):
        tt.retrieval_features(val, probs, embed_search=bad_search, mask_pii=lambda t: (t, {}),
                              build_text=lambda s, b: b, pre_draft_gate=None)


def test_run_writes_report_and_json(tmp_path):
    f = _synthetic()
    summary = tt.run(f, tmp_path, demo08_sim=0.30)
    md = (tmp_path / "threshold_sweep.md").read_text(encoding="utf-8")
    js = json.loads((tmp_path / "threshold_sweep.json").read_text(encoding="utf-8"))
    assert js == json.loads(json.dumps(summary))
    assert set(js["recommended"]) == set(tt.TH_COLS)
    assert js["demo08_sanity"]["below"] == (0.30 < js["recommended"]["T_SIM"])
    for needle in ("Recommended row", "agent/config.py", "demo-08", "One threshold at a time",
                   "Val top-1 similarity distribution", "T_SIM = "):
        assert needle in md
    assert md.isascii()


def test_load_val_uses_only_val_rows(tmp_path):
    kb = pd.DataFrame({"ticket_id": ["A", "B", "C"], "subject": "s", "body": "b", "answer": "x",
                       "type": "Incident", "priority": "high", "is_val": [False, True, True]})
    kb.to_parquet(tmp_path / "kb_train.parquet", index=False)
    (tmp_path / "test_labels.parquet").write_text("must never be read")
    val = tt.load_val(tmp_path)
    assert list(val["ticket_id"]) == ["B", "C"]
    assert "answer" not in val.columns and "is_val" not in val.columns


def test_script_never_references_test_files():
    src = Path(tt.__file__).read_text(encoding="utf-8")
    assert "test_labels" not in src and "test_inputs" not in src
