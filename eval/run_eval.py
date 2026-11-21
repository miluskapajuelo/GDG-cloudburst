"""Holdout evaluation (A2.3) and LLM sample evaluation (A2.5).

Run from the repo root:
    python -m eval.run_eval                      # full holdout run (skip_llm)
    python -m eval.run_eval --limit 200          # quick partial run
    python -m eval.run_eval --check-only         # leakage asserts + split fingerprint, then exit
    python -m eval.run_eval --llm-sample 40      # + 40 stratified tickets with the LLM on (max 3 runs)

Leakage order (docs/data-and-leakage.md):
  1. Read kb_train.parquet (ticket_id, is_val only) and test_inputs.parquet. Re-check the asserts,
     print row counts and the split fingerprint.
  2. Run every test input through the triage function (api.service.triage, skip_llm=True, in-process:
     the same code path as the demo). Only subject and body are passed in.
  3. Write test_predictions.parquet.
  3b. (--llm-sample N) Pick N tickets from those PREDICTIONS (>= 10 predicted high/Incident, en/de mix), run
     them with skip_llm=False, write llm_samples.jsonl. Still no labels involved.
  4. Only then read test_labels.parquet (load_labels is the only reader in the repo) and score.
  5. Write metrics.json (shape: docs/tasks/team-a-ml-eval.md, A2.6) and metrics.md.

Per-row test labels are never printed or logged. Only aggregate metrics are written.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import time
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HEADS = ("type", "queue", "priority")
LABEL_COLS = ("type", "queue", "priority", "language")
STAGES = ("pii", "language", "classify", "retrieve", "gate", "generate", "total")
PRE_DRAFT_CODES = (
    "PROMPT_INJECTION_SUSPECTED",
    "HIGH_PRIORITY_INCIDENT",
    "LOW_CLASSIFIER_CONFIDENCE",
    "NO_PRECEDENT",
    "UNSUPPORTED_REQUEST",
)
EXPECTED_FINGERPRINT = "5a2ede85f9fb"  # docs/data-and-leakage.md section 6
ERROR_STATUS = "ERROR"
ERROR_LABEL = "(error)"  # predicted label for rows whose triage call raised; always counted as wrong
PROGRESS_EVERY = 250

TriageFn = Callable[..., dict]


# ---------------------------------------------------------------- paths and inputs

def data_dir() -> Path:
    return Path(os.getenv("SENTINEL_DATA_DIR", "data"))


def split_fingerprint(ticket_ids: Iterable[str]) -> str:
    """sha256 of the test ticket IDs in file order, joined with commas (data-and-leakage section 3)."""
    return hashlib.sha256(",".join(ticket_ids).encode()).hexdigest()[:12]


def load_inputs(ddir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (kb, test_inputs). Never touches test_labels.parquet."""
    kb = pd.read_parquet(ddir / "kb_train.parquet", columns=["ticket_id", "is_val"])
    test_inputs = pd.read_parquet(ddir / "test_inputs.parquet")
    return kb, test_inputs


def check_leakage(kb: pd.DataFrame, test_inputs: pd.DataFrame) -> str:
    """Re-check the data-and-leakage section 3 asserts on the full test inputs. Return the fingerprint."""
    assert "answer" not in test_inputs.columns, "LEAKAGE: test_inputs has an 'answer' column"
    extra = set(test_inputs.columns) & {"type", "queue", "priority", "language", "tags"}
    assert not extra, f"LEAKAGE: test_inputs has label columns {sorted(extra)}"
    assert set(kb["ticket_id"]).isdisjoint(test_inputs["ticket_id"]), "LEAKAGE: KB and test ticket IDs overlap"
    assert test_inputs["ticket_id"].is_unique, "test_inputs has duplicate ticket IDs"

    n_val = int(kb["is_val"].sum())
    print(f"[eval] rows: kb={len(kb)} (fit={len(kb) - n_val}, val={n_val})  test={len(test_inputs)}")
    print("[eval] leakage asserts passed: no answer column, KB/test IDs disjoint")
    fp = split_fingerprint(test_inputs["ticket_id"])
    verdict = "matches" if fp == EXPECTED_FINGERPRINT else f"DOES NOT MATCH expected {EXPECTED_FINGERPRINT}"
    print(f"[eval] split fingerprint: {fp} ({verdict})")
    return fp


def load_labels(ddir: Path) -> pd.DataFrame:
    """The ONLY reader of test_labels.parquet. Call it after test_predictions.parquet is written."""
    labels = pd.read_parquet(ddir / "test_labels.parquet")
    assert "answer" not in labels.columns, "LEAKAGE: test_labels has an 'answer' column"
    return labels


# ---------------------------------------------------------------- prediction

def _flatten(ticket_id: str, resp: dict, wall_ms: int) -> dict[str, Any]:
    preds = resp.get("predictions") or {}
    esc = resp.get("escalation") or {}
    lang = resp.get("language") or {}
    lat = resp.get("latency_ms") or {}
    row: dict[str, Any] = {"ticket_id": ticket_id}
    for head in HEADS:
        p = preds.get(head) or {}
        row[f"{head}_label"] = p.get("label")
        conf = p.get("confidence")
        row[f"{head}_conf"] = float(conf) if conf is not None else None
    row["status"] = esc.get("status")
    row["route"] = esc.get("route")
    row["reason_codes"] = "|".join(r.get("code", "") for r in esc.get("reasons") or [])
    row["lang_code"] = lang.get("code")
    for stage in STAGES:
        row[f"lat_{stage}"] = int(lat.get(stage, 0) or 0)
    row["wall_ms"] = wall_ms
    row["error"] = None
    return row


def _error_row(ticket_id: str, exc: Exception) -> dict[str, Any]:
    row: dict[str, Any] = {"ticket_id": ticket_id}
    for head in HEADS:
        row[f"{head}_label"] = None
        row[f"{head}_conf"] = None
    row.update(status=ERROR_STATUS, route=None, reason_codes="", lang_code=None)
    for stage in STAGES:
        row[f"lat_{stage}"] = 0
    row["wall_ms"] = 0
    row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return row


def predict(test_inputs: pd.DataFrame, triage_fn: TriageFn, *, progress_every: int = PROGRESS_EVERY) -> pd.DataFrame:
    """Run every test input through triage_fn(subject, body, skip_llm=True). Only subject and body go in."""
    rows: list[dict[str, Any]] = []
    n = len(test_inputs)
    n_err = 0
    t0 = time.perf_counter()
    for i, (tid, subject, body) in enumerate(
        zip(test_inputs["ticket_id"], test_inputs["subject"], test_inputs["body"]), start=1
    ):
        subject = subject if isinstance(subject, str) else ""
        body = body if isinstance(body, str) else ""
        start = time.perf_counter()
        try:
            resp = triage_fn(subject, body, skip_llm=True)
            rows.append(_flatten(str(tid), resp, int(round((time.perf_counter() - start) * 1000))))
        except Exception as exc:  # one bad row must not kill a 5,718-row run
            n_err += 1
            rows.append(_error_row(str(tid), exc))
            if n_err <= 3:
                print(f"[eval] triage error on {tid}: {rows[-1]['error']}", flush=True)
        if i % progress_every == 0 or i == n:
            print(f"[eval] {i}/{n} rows  {time.perf_counter() - t0:.1f}s  errors={n_err}", flush=True)
    return pd.DataFrame(rows)


def save_predictions(preds: pd.DataFrame, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "test_predictions.parquet"
    preds.to_parquet(path, index=False)
    print(f"[eval] wrote {path} ({len(preds)} rows)")
    return path


# ---------------------------------------------------------------- LLM sample (A2.5)
#
# The sample is drawn from the skip_llm PREDICTIONS (predicted high/Incident, detected language), never
# from test labels, and it runs before test_labels.parquet is read. Each sampled ticket goes through
# triage(subject, body, skip_llm=False): the same code path as the live demo, LLM included.

LLM_SAMPLE_MIN_HPI = 10
LLM_SAMPLE_MAX_RUNS = 3  # A2.5: LLM calls cost money and time
LLM_RUNS_FILE = "llm_sample_runs.json"
LLM_SEED = 42
DetectFn = Callable[[str], dict]


def select_llm_sample(preds: pd.DataFrame, n: int, *, seed: int = LLM_SEED,
                      min_hpi: int = LLM_SAMPLE_MIN_HPI) -> list[str]:
    """Pick n ticket IDs from the skip_llm predictions: at least min_hpi predicted high and Incident
    (or all of them, if fewer exist), the rest from the other tickets. Inside each stratum, half come
    from tickets detected as German and half from the others, so the sample mixes en and de."""
    ok = preds[preds["status"] != ERROR_STATUS]
    n = min(n, len(ok))
    if n <= 0:
        return []
    rng = np.random.default_rng(seed)
    is_hpi = (ok["priority_label"] == "high") & (ok["type_label"] == "Incident")
    hpi, rest = ok[is_hpi], ok[~is_hpi]
    k_hpi = min(len(hpi), max(min_hpi, n // 4), n)
    k_rest = min(n - k_hpi, len(rest))
    k_hpi = min(len(hpi), n - k_rest)  # top up from HPI if the other stratum is small

    def take(pool: pd.DataFrame, k: int) -> list[str]:
        if k <= 0:
            return []
        de = pool[pool["lang_code"] == "de"]["ticket_id"].tolist()
        other = pool[pool["lang_code"] != "de"]["ticket_id"].tolist()
        rng.shuffle(de)
        rng.shuffle(other)
        k_de = min(len(de), k // 2)
        k_other = min(len(other), k - k_de)
        k_de = min(len(de), k - k_other)
        return de[:k_de] + other[:k_other]

    picked = set(take(hpi, k_hpi) + take(rest, k_rest))
    return [tid for tid in ok["ticket_id"] if tid in picked]  # keep test-file order


def _codes(resp: dict) -> list[str]:
    return [r.get("code", "") for r in (resp.get("escalation") or {}).get("reasons") or []]


def _sample_record(ticket_id: str, resp: dict, wall_ms: int) -> dict[str, Any]:
    """One llm_samples.jsonl line. Model outputs only: no test labels, no test answers, no ticket text."""
    preds = resp.get("predictions") or {}
    return {
        "ticket_id": ticket_id,
        "predictions": {h: {"label": (preds.get(h) or {}).get("label"),
                            "confidence": (preds.get(h) or {}).get("confidence")} for h in HEADS},
        "language": resp.get("language"),
        "escalation": resp.get("escalation"),
        "precedent_ids": [p.get("ticket_id") for p in resp.get("precedents") or []],
        "draft": resp.get("draft"),
        "latency_ms": resp.get("latency_ms"),
        "wall_ms": wall_ms,
        "error": None,
    }


def _rate(num: int, den: int) -> float:
    return _r(num / den) if den else 0.0


def score_llm_sample(records: list[dict[str, Any]], detect_fn: DetectFn) -> dict[str, Any]:
    """Grounding and with-LLM latency over the sampled responses. Needs no labels at all.

    Denominators:
      citation_valid_rate         drafts returned (draft not null) without CITATION_CHECK_FAILED
      draft_with_citation_rate    OK drafts with at least one cited ID
      insufficient_evidence_rate  all sampled tickets
      llm_unavailable_rate        all sampled tickets
      reply_language_match_rate   drafts with text whose detected language == language.reply_language
    """
    ok = [r for r in records if not r["error"]]
    n = len(ok)
    drafts = [r for r in ok if r["draft"]]
    ok_drafts = [r for r in drafts if r["draft"].get("status") == "OK"]
    texts = [r for r in drafts if (r["draft"].get("text") or "").strip()]
    cit_failed = sum("CITATION_CHECK_FAILED" in _codes(r) for r in drafts)
    insufficient = sum(
        (r["draft"] or {}).get("status") == "INSUFFICIENT_EVIDENCE" or "LLM_INSUFFICIENT_EVIDENCE" in _codes(r)
        for r in ok
    )
    unavailable = sum("LLM_UNAVAILABLE" in _codes(r) for r in ok)
    lang_match = sum(
        str(detect_fn(r["draft"]["text"]).get("code")) == str((r["language"] or {}).get("reply_language"))
        for r in texts
    )
    totals = pd.Series([int((r["latency_ms"] or {}).get("total", 0) or 0) for r in ok], dtype="int64")
    gens = pd.Series([g for g in (int((r["latency_ms"] or {}).get("generate", 0) or 0) for r in ok) if g > 0],
                     dtype="int64")
    escalated = [r for r in ok if (r["escalation"] or {}).get("status") == "ESCALATE"]
    return {
        "grounding": {
            "n": n,
            "citation_valid_rate": _rate(len(drafts) - cit_failed, len(drafts)),
            "draft_with_citation_rate": _rate(sum(bool(r["draft"].get("cited_ids")) for r in ok_drafts),
                                              len(ok_drafts)),
            "insufficient_evidence_rate": _rate(insufficient, n),
            "llm_unavailable_rate": _rate(unavailable, n),
            "reply_language_match_rate": _rate(lang_match, len(texts)),
        },
        "with_llm": {
            "p50": _pct(totals, 50), "p95": _pct(totals, 95),
            "generate_p50": _pct(gens, 50), "generate_p95": _pct(gens, 95),
            "n": n,
        },
        "detail": {
            "n_requested": len(records),
            "n_errors": len(records) - n,
            "n_llm_calls": int(len(gens)),
            "n_drafts": len(drafts),
            "n_ok_drafts": len(ok_drafts),
            "n_citation_failed": cit_failed,
            "n_insufficient_evidence": insufficient,
            "n_llm_unavailable": unavailable,
            "n_lang_checked": len(texts),
            "n_lang_match": lang_match,
            "n_predicted_hpi": sum(
                (r["predictions"]["priority"]["label"] == "high") and (r["predictions"]["type"]["label"] == "Incident")
                for r in ok
            ),
            "n_reply_de": sum((r["language"] or {}).get("reply_language") == "de" for r in ok),
            "n_escalated": len(escalated),
            "reason_counts": dict(Counter(c for r in ok for c in _codes(r) if c)),
        },
    }


def _bump_run_counter(out_dir: Path, *, force: bool) -> int:
    """Count LLM sample runs in out_dir/llm_sample_runs.json. Refuse a 4th run unless force is set."""
    path = out_dir / LLM_RUNS_FILE
    try:
        runs = json.loads(path.read_text(encoding="utf-8")).get("runs", [])
    except (OSError, ValueError):
        runs = []
    if len(runs) >= LLM_SAMPLE_MAX_RUNS and not force:
        raise RuntimeError(
            f"the LLM sample already ran {len(runs)} times (limit {LLM_SAMPLE_MAX_RUNS}, see {path}). "
            "Pass --force-llm-sample to run it anyway."
        )
    runs.append(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"runs": runs}, indent=2) + "\n", encoding="utf-8")
    return len(runs)


def run_llm_sample(
    test_inputs: pd.DataFrame,
    preds: pd.DataFrame,
    triage_fn: TriageFn,
    detect_fn: DetectFn,
    *,
    n: int,
    out_dir: Path,
    force: bool = False,
    reset_fn: Callable[[], None] | None = None,
) -> dict[str, Any] | None:
    """Run the stratified sample with skip_llm=False, write llm_samples.jsonl, return the scored sample."""
    ids = select_llm_sample(preds, n)
    if not ids:
        print("[eval] LLM sample: no eligible tickets, skipped")
        return None
    run_no = _bump_run_counter(out_dir, force=force)
    print(f"[eval] LLM sample run {run_no}/{LLM_SAMPLE_MAX_RUNS}: {len(ids)} tickets with skip_llm=False ...")
    if reset_fn is not None:
        reset_fn()  # the full skip_llm pass filled the burst window; start the sample clean
    rows = test_inputs.set_index("ticket_id").loc[ids, ["subject", "body"]]
    records: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for i, (tid, subject, body) in enumerate(zip(rows.index, rows["subject"], rows["body"]), start=1):
        subject = subject if isinstance(subject, str) else ""
        body = body if isinstance(body, str) else ""
        start = time.perf_counter()
        try:
            resp = triage_fn(subject, body, skip_llm=False)
            records.append(_sample_record(str(tid), resp, int(round((time.perf_counter() - start) * 1000))))
        except Exception as exc:
            rec = {"ticket_id": str(tid), "predictions": None, "language": None, "escalation": None,
                   "precedent_ids": [], "draft": None, "latency_ms": None, "wall_ms": 0,
                   "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            records.append(rec)
            print(f"[eval] LLM sample error on {tid}: {rec['error']}", flush=True)
        if i % 10 == 0 or i == len(ids):
            print(f"[eval] LLM sample {i}/{len(ids)}  {time.perf_counter() - t0:.1f}s", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "llm_samples.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(to_plain(rec), ensure_ascii=False) + "\n")
    print(f"[eval] wrote {path} ({len(records)} rows)")

    result = score_llm_sample(records, detect_fn)
    result["detail"]["run"] = run_no
    if result["detail"]["n_llm_calls"] == 0:
        print("[eval] WARNING: the LLM sample made no LLM calls. Check /health: PII masking or the pipeline "
              "may still be a stub, or GEMINI_API_KEY is missing.")
    return result


_DE_HINTS = {"der", "die", "das", "und", "ist", "nicht", "mit", "wir", "ihre", "ihr", "sie", "bitte", "vielen",
             "dank", "freundlichen", "grüßen", "für", "bei", "auf", "eine", "einen", "wurde", "können"}
_EN_HINTS = {"the", "and", "is", "not", "with", "we", "your", "you", "please", "thank", "thanks", "regards",
             "for", "on", "a", "an", "was", "can", "have", "this", "that", "to", "of"}


def fallback_detect_language(text: str) -> dict:
    """Function-word vote, used only when agent.lang (lingua) is not installed."""
    tokens = [t.strip(".,;:!?()[]\"'").lower() for t in text.split()]
    de = sum(t in _DE_HINTS for t in tokens)
    en = sum(t in _EN_HINTS for t in tokens)
    code = "de" if de > en else "en"
    return {"code": code, "confidence": 0.0, "reply_language": code}


def load_detector() -> DetectFn:
    """The same detector the API uses (agent.lang), or the fallback if it is not available."""
    try:
        from agent.lang import detect_language
        return detect_language
    except ImportError as exc:
        print(f"[eval] agent.lang not available ({exc}); reply-language check uses a function-word fallback")
        return fallback_detect_language


# ---------------------------------------------------------------- scoring

def _r(x: float) -> float:
    return round(float(x), 4)


def _pct(values: pd.Series, q: float) -> int:
    return int(round(float(np.percentile(values, q)))) if len(values) else 0


def _head_scores(y_true: pd.Series, y_pred: pd.Series) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

    # Labels = union of true and predicted labels. Error rows stay in y_pred as ERROR_LABEL, so they count
    # as misses for their true class without adding a phantom class to the macro average.
    labels = sorted((set(y_true) | set(y_pred)) - {ERROR_LABEL})
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm_cols = labels + ([ERROR_LABEL] if (y_pred == ERROR_LABEL).any() else [])
    cm = confusion_matrix(y_true, y_pred, labels=cm_cols)
    return {
        "macro_f1": _r(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": _r(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
        "accuracy": _r(accuracy_score(y_true, y_pred)),
        "per_class": {
            lab: {
                "precision": _r(report[lab]["precision"]),
                "recall": _r(report[lab]["recall"]),
                "f1": _r(report[lab]["f1-score"]),
                "support": int(report[lab]["support"]),
            }
            for lab in labels
        },
        "confusion": {"rows": labels, "cols": cm_cols, "matrix": [[int(v) for v in r] for r in cm[: len(labels)]]},
    }


def score(preds: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    """Score saved predictions against the test labels. Returns aggregates only (plus per-class tables)."""
    assert "answer" not in labels.columns, "LEAKAGE: test_labels has an 'answer' column"
    missing = set(preds["ticket_id"]) - set(labels["ticket_id"])
    assert not missing, f"{len(missing)} predicted ticket IDs are missing from test_labels"
    merged = preds.merge(labels[["ticket_id", *LABEL_COLS]], on="ticket_id", how="left", validate="one_to_one")
    n = len(merged)
    is_err = merged["status"] == ERROR_STATUS

    heads: dict[str, Any] = {}
    for head in HEADS:
        y_true = merged[head].astype(str)
        y_pred = merged[f"{head}_label"].where(~is_err, ERROR_LABEL).fillna(ERROR_LABEL).astype(str)
        heads[head] = _head_scores(y_true, y_pred)

    # High-priority incidents. Error rows count as misses for both recalls.
    true_hpi = (merged["priority"] == "high") & (merged["type"] == "Incident")
    pred_hpi = (merged["priority_label"] == "high") & (merged["type_label"] == "Incident")
    escalated = merged["status"] == "ESCALATE"
    support = int(true_hpi.sum())
    hpi = {
        "support": support,
        "classifier_recall": _r((true_hpi & pred_hpi).sum() / support) if support else 0.0,
        "escalation_recall": _r((true_hpi & escalated).sum() / support) if support else 0.0,
    }
    # Outcome per ticket: "ESCALATE / ON_CALL", "ESCALATE / HUMAN_REVIEW", "AUTO_DRAFT" or "ERROR".
    outcome = merged["status"].fillna("none").where(~escalated, "ESCALATE / " + merged["route"].fillna("none"))
    hpi_routes = {str(k): int(v) for k, v in outcome[true_hpi].value_counts().items()}

    # Escalation: rate over all rows, and every reason code of every ticket (not just the first one).
    reason_counts: dict[str, int] = {code: 0 for code in PRE_DRAFT_CODES}
    seen = Counter(c for codes in merged["reason_codes"].fillna("") for c in codes.split("|") if c)
    for code in sorted(seen):
        reason_counts[code] = int(seen[code])
    escalation = {"rate": _r(escalated.mean()) if n else 0.0, "reason_counts": reason_counts}
    route_counts = {str(k): int(v) for k, v in outcome.value_counts().items()}

    # Language. The label is noisy (agent/NOTES.md: ~29% of "de" rows are English text), so also break it down.
    lang_ok = merged["lang_code"] == merged["language"]
    lang_detail = {
        str(lab): {
            "n": int(grp.shape[0]),
            "accuracy": _r(lang_ok[grp.index].mean()),
            "detected": {str(k): int(v) for k, v in grp["lang_code"].fillna("(none)").value_counts().items()},
        }
        for lab, grp in merged.groupby("language")
    }

    # Latency over the rows that did not error.
    ok = merged.loc[~is_err]
    latency_skip = {"p50": _pct(ok["lat_total"], 50), "p95": _pct(ok["lat_total"], 95), "n": int(len(ok))}
    stages = {s: {"p50": _pct(ok[f"lat_{s}"], 50), "p95": _pct(ok[f"lat_{s}"], 95)} for s in STAGES if s != "total"}
    stages["eval_wall"] = {"p50": _pct(ok["wall_ms"], 50), "p95": _pct(ok["wall_ms"], 95)}

    errors = merged.loc[is_err, "error"].fillna("").tolist()
    return {
        "n": n,
        "n_errors": int(is_err.sum()),
        "error_types": dict(Counter(e.split(":", 1)[0] for e in errors)),
        "heads": heads,
        "high_priority_incident": hpi,
        "hpi_routes": hpi_routes,
        "escalation": escalation,
        "route_counts": route_counts,
        "language_detection_accuracy": _r(lang_ok.mean()) if n else 0.0,
        "language_detail": lang_detail,
        "latency_skip_llm": latency_skip,
        "latency_skip_llm_stages": stages,
    }


# ---------------------------------------------------------------- metrics.json / metrics.md

def to_plain(obj: Any) -> Any:
    """Recursively convert numpy / pandas scalars to plain Python types for json."""
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def build_metrics(scores: dict[str, Any], fingerprint: str, thresholds: dict[str, Any],
                  llm: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble metrics.json exactly as in A2.6 (+ latency_ms.skip_llm_stages).
    llm is the score_llm_sample result (A2.5); without it the with_llm and grounding blocks stay at n=0."""
    metrics = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "split_fingerprint": fingerprint,
        "n_test": scores["n"],
        "classifier": {
            h: {k: scores["heads"][h][k] for k in ("macro_f1", "weighted_f1", "accuracy")} for h in HEADS
        },
        "high_priority_incident": scores["high_priority_incident"],
        "escalation": scores["escalation"],
        "language_detection_accuracy": scores["language_detection_accuracy"],
        "latency_ms": {
            "skip_llm": scores["latency_skip_llm"],
            "with_llm": dict(llm["with_llm"]) if llm else
            {"p50": 0, "p95": 0, "generate_p50": 0, "generate_p95": 0, "n": 0},
            "skip_llm_stages": scores["latency_skip_llm_stages"],
        },
        "grounding": dict(llm["grounding"]) if llm else {
            "n": 0,
            "citation_valid_rate": 0.0,
            "draft_with_citation_rate": 0.0,
            "insufficient_evidence_rate": 0.0,
            "llm_unavailable_rate": 0.0,
            "reply_language_match_rate": 0.0,
        },
        "thresholds": dict(thresholds),
    }
    return to_plain(metrics)


def _table(header: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def _llm_md(metrics: dict[str, Any], llm: dict[str, Any]) -> list[str]:
    g, w, d = metrics["grounding"], metrics["latency_ms"]["with_llm"], llm["detail"]
    lines = [
        "## LLM sample (grounding, skip_llm=False)",
        "",
        f"Run {d['run']} of at most {LLM_SAMPLE_MAX_RUNS}. Sampled {d['n_requested']} test inputs, stratified on the"
        f" skip_llm predictions (never on labels): {d['n_predicted_hpi']} predicted high/Incident,"
        f" {d['n_reply_de']} with German reply language. Errors: {d['n_errors']}. LLM calls made: {d['n_llm_calls']}.",
        "Drafts are in `eval/results/llm_samples.jsonl` (model outputs only: no labels, no test answers).",
        "",
    ]
    lines += _table(
        ["Metric", "Value", "Count", "Denominator"],
        [
            ["Citation validity (no CITATION_CHECK_FAILED)", f"{g['citation_valid_rate']:.4f}",
             d["n_drafts"] - d["n_citation_failed"], f"{d['n_drafts']} drafts returned"],
            ["OK drafts with at least 1 citation", f"{g['draft_with_citation_rate']:.4f}",
             round(g["draft_with_citation_rate"] * d["n_ok_drafts"]), f"{d['n_ok_drafts']} OK drafts"],
            ["INSUFFICIENT_EVIDENCE rate", f"{g['insufficient_evidence_rate']:.4f}", d["n_insufficient_evidence"],
             f"{g['n']} sampled tickets"],
            ["LLM_UNAVAILABLE rate", f"{g['llm_unavailable_rate']:.4f}", d["n_llm_unavailable"],
             f"{g['n']} sampled tickets"],
            ["Reply-language match", f"{g['reply_language_match_rate']:.4f}", d["n_lang_match"],
             f"{d['n_lang_checked']} drafts with text"],
        ],
    )
    lines += ["Latency with the LLM (ms):", ""]
    lines += _table(["Measure", "p50", "p95", "n"],
                    [["total (all sampled tickets)", w["p50"], w["p95"], w["n"]],
                     ["generate (tickets with an LLM call)", w["generate_p50"], w["generate_p95"], d["n_llm_calls"]]])
    if d["reason_counts"]:
        lines += ["Reason codes in the sample:", ""]
        lines += _table(["Reason code", "Count"], [[k, v] for k, v in sorted(d["reason_counts"].items())])
    return lines


def render_md(metrics: dict[str, Any], scores: dict[str, Any], *, limit: int | None, llm_sample: int,
              llm: dict[str, Any] | None = None) -> str:
    n = metrics["n_test"]
    lines = [
        "# SentinelDesk holdout metrics",
        "",
        f"- Generated: {metrics['generated_at']}",
        f"- Split fingerprint: `{metrics['split_fingerprint']}`",
        f"- Test tickets scored: {n}" + (f" (PARTIAL RUN: --limit {limit})" if limit else ""),
        f"- Triage errors: {scores['n_errors']} (counted as wrong predictions and as not escalated)",
        "- Mode: `api.service.triage(subject, body, skip_llm=True)`, in-process, one ticket at a time",
        "- LLM sample: "
        + ("not run (use --llm-sample N)" if llm_sample <= 0 or not llm
           else f"{llm['grounding']['n']} tickets with skip_llm=False (section below)"),
        "",
        "## Classifier",
        "",
    ]
    lines += _table(
        ["Head", "Macro-F1", "Weighted-F1", "Accuracy"],
        [[h, f"{m['macro_f1']:.4f}", f"{m['weighted_f1']:.4f}", f"{m['accuracy']:.4f}"]
         for h, m in metrics["classifier"].items()],
    )

    hpi = metrics["high_priority_incident"]
    lines += ["## High-priority incidents (true priority=high and type=Incident)", ""]
    lines += _table(
        ["Support", "Classifier recall (pred high and Incident)", "Escalation recall (status ESCALATE)"],
        [[hpi["support"], f"{hpi['classifier_recall']:.4f}", f"{hpi['escalation_recall']:.4f}"]],
    )
    lines += ["Outcome of the true high-priority incidents:", ""]
    lines += _table(["Outcome", "Count"], [[k, v] for k, v in scores["hpi_routes"].items()])

    esc = metrics["escalation"]
    lines += ["## Escalation", "", f"Escalation rate: {esc['rate']:.4f}", ""]
    lines += _table(["Outcome", "Count"], [[k, v] for k, v in scores["route_counts"].items()])
    lines += ["Reason codes (every reason of every ticket is counted):", ""]
    lines += _table(["Reason code", "Count", "Share of tickets"],
                    [[k, v, f"{v / n:.4f}" if n else "0"] for k, v in esc["reason_counts"].items()])

    lines += [
        "## Language detection",
        "",
        f"Accuracy against the `language` label: {metrics['language_detection_accuracy']:.4f}",
        "",
        "Caveat: the `language` label is noisy. B1 found that about 29% of KB rows labelled `de` are English text"
        " (agent/NOTES.md), so disagreement on `de` rows is mostly label noise, not detector error.",
        "",
    ]
    lines += _table(
        ["Label", "Rows", "Accuracy", "Detected as"],
        [[lab, d["n"], f"{d['accuracy']:.4f}", ", ".join(f"{k}: {v}" for k, v in d["detected"].items())]
         for lab, d in scores["language_detail"].items()],
    )

    lat = metrics["latency_ms"]
    lines += ["## Latency (ms, skip_llm)", "", f"Rows timed: {lat['skip_llm']['n']}", ""]
    stage_rows = [[s, v["p50"], v["p95"]] for s, v in lat["skip_llm_stages"].items()]
    stage_rows.append(["**total**", lat["skip_llm"]["p50"], lat["skip_llm"]["p95"]])
    lines += _table(["Stage", "p50", "p95"], stage_rows)
    lines += ["`eval_wall` is the wall time of the `triage()` call measured by the eval script.", ""]

    if llm:
        lines += _llm_md(metrics, llm)

    lines += ["## Thresholds (from `api.service.get_config()`)", ""]
    lines += _table(["Name", "Value"], [[k, v] for k, v in metrics["thresholds"].items()])

    for head in HEADS:
        d = scores["heads"][head]
        lines += [f"## Per-class report: {head}", ""]
        lines += _table(
            ["Label", "Precision", "Recall", "F1", "Support"],
            [[lab, f"{m['precision']:.4f}", f"{m['recall']:.4f}", f"{m['f1']:.4f}", m["support"]]
             for lab, m in d["per_class"].items()],
        )
        cm = d["confusion"]
        lines += [f"Confusion matrix: {head} (rows = true, columns = predicted)", ""]
        lines += _table(["true \\ pred", *cm["cols"]], [[lab, *row] for lab, row in zip(cm["rows"], cm["matrix"])])

    if scores["n_errors"]:
        lines += ["## Triage errors", ""]
        lines += _table(["Exception", "Count"], [[k, v] for k, v in scores["error_types"].items()])
    return "\n".join(lines)


def write_outputs(metrics: dict[str, Any], md: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (out_dir / "metrics.md").write_text(md + "\n", encoding="utf-8")
    print(f"[eval] wrote {out_dir / 'metrics.json'} and {out_dir / 'metrics.md'}")


# ---------------------------------------------------------------- orchestration

def run_eval(
    test_inputs: pd.DataFrame,
    triage_fn: TriageFn,
    *,
    ddir: Path,
    out_dir: Path,
    fingerprint: str,
    thresholds: dict[str, Any],
    limit: int | None = None,
    llm_sample: int = 0,
    detect_fn: DetectFn | None = None,
    force_llm_sample: bool = False,
    reset_fn: Callable[[], None] | None = None,
    progress_every: int = PROGRESS_EVERY,
) -> dict[str, Any]:
    """Predict, save predictions, run the LLM sample (if asked), THEN load labels and score.
    Returns the metrics.json dict."""
    if limit:
        test_inputs = test_inputs.head(limit)
        print(f"[eval] --limit {limit}: scoring the first {len(test_inputs)} test inputs (partial run)")
    print(f"[eval] triaging {len(test_inputs)} tickets with skip_llm=True ...")
    preds = predict(test_inputs, triage_fn, progress_every=progress_every)
    pred_path = save_predictions(preds, out_dir)

    # A2.5: the LLM sample is chosen from the predictions and runs before any label is read.
    llm = None
    if llm_sample > 0:
        llm = run_llm_sample(test_inputs, preds, triage_fn, detect_fn or fallback_detect_language, n=llm_sample,
                             out_dir=out_dir, force=force_llm_sample, reset_fn=reset_fn)

    # Scoring step. test_labels.parquet is read here for the first time, after predictions are on disk.
    labels = load_labels(ddir)
    scores = score(pd.read_parquet(pred_path), labels)
    del labels

    metrics = build_metrics(scores, fingerprint, thresholds, llm)
    write_outputs(metrics, render_md(metrics, scores, limit=limit, llm_sample=llm_sample, llm=llm), out_dir)
    c = metrics["classifier"]
    hpi = metrics["high_priority_incident"]
    print(
        "[eval] macro-F1 type={:.4f} queue={:.4f} priority={:.4f} | HPI support={} clf_recall={:.4f} "
        "esc_recall={:.4f} | escalation rate={:.4f} | errors={}".format(
            c["type"]["macro_f1"], c["queue"]["macro_f1"], c["priority"]["macro_f1"], hpi["support"],
            hpi["classifier_recall"], hpi["escalation_recall"], metrics["escalation"]["rate"], scores["n_errors"],
        )
    )
    if llm:
        g, w = metrics["grounding"], metrics["latency_ms"]["with_llm"]
        print(
            "[eval] LLM sample n={} | citation_valid={:.4f} with_citation={:.4f} insufficient={:.4f} "
            "unavailable={:.4f} lang_match={:.4f} | total p50/p95={}/{} ms generate p50/p95={}/{} ms".format(
                g["n"], g["citation_valid_rate"], g["draft_with_citation_rate"], g["insufficient_evidence_rate"],
                g["llm_unavailable_rate"], g["reply_language_match_rate"], w["p50"], w["p95"],
                w["generate_p50"], w["generate_p95"],
            )
        )
    return metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SentinelDesk holdout evaluation (A2.3, A2.5)")
    ap.add_argument("--limit", type=int, default=None, help="score only the first N test inputs")
    ap.add_argument("--llm-sample", type=int, default=0,
                    help="also run N stratified test inputs with the LLM on (A2.5; at most 3 runs per --out)")
    ap.add_argument("--force-llm-sample", action="store_true", help="ignore the 3-run limit of the LLM sample")
    ap.add_argument("--out", type=Path, default=Path("eval/results"), help="output folder")
    ap.add_argument("--check-only", action="store_true", help="run the leakage asserts and fingerprint, then exit")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ddir = data_dir()
    kb, test_inputs = load_inputs(ddir)
    fingerprint = check_leakage(kb, test_inputs)  # on the full test inputs, before --limit
    del kb
    if args.check_only:
        return 0

    try:  # lazy import: tests and --check-only work without the service
        service = importlib.import_module("api.service")
    except ModuleNotFoundError as exc:
        if exc.name not in ("api.service", "api"):
            raise  # a dependency inside the service is missing: show the real error
        print("[eval] ERROR: api.service is not available (task A2.2). Nothing was scored.")
        return 2
    service.startup()
    run_eval(
        test_inputs,
        service.triage,
        ddir=ddir,
        out_dir=args.out,
        fingerprint=fingerprint,
        thresholds=service.get_config(),
        limit=args.limit,
        llm_sample=args.llm_sample,
        detect_fn=load_detector() if args.llm_sample > 0 else None,
        force_llm_sample=args.force_llm_sample,
        reset_fn=getattr(service, "reset_burst", None),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
