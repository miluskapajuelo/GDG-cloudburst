"""Holdout evaluation (A2.3).

Run from the repo root:
    python -m eval.run_eval                      # full holdout run (skip_llm)
    python -m eval.run_eval --limit 200          # quick partial run
    python -m eval.run_eval --check-only         # leakage asserts + split fingerprint, then exit

Leakage order (docs/data-and-leakage.md):
  1. Read kb_train.parquet (ticket_id, is_val only) and test_inputs.parquet. Re-check the asserts,
     print row counts and the split fingerprint.
  2. Run every test input through the triage function (api.service.triage, skip_llm=True, in-process:
     the same code path as the demo). Only subject and body are passed in.
  3. Write test_predictions.parquet.
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


def build_metrics(scores: dict[str, Any], fingerprint: str, thresholds: dict[str, Any]) -> dict[str, Any]:
    """Assemble metrics.json exactly as in A2.6 (+ latency_ms.skip_llm_stages)."""
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
            # A2.5 (--llm-sample) fills these. Zeros with n=0 until then.
            "with_llm": {"p50": 0, "p95": 0, "generate_p50": 0, "generate_p95": 0, "n": 0},
            "skip_llm_stages": scores["latency_skip_llm_stages"],
        },
        "grounding": {
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


def render_md(metrics: dict[str, Any], scores: dict[str, Any], *, limit: int | None, llm_sample: int) -> str:
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
        + ("not run (task A2.5)" if llm_sample <= 0 else f"requested {llm_sample}, not implemented yet (task A2.5)"),
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
    progress_every: int = PROGRESS_EVERY,
) -> dict[str, Any]:
    """Predict, save predictions, THEN load labels and score. Returns the metrics.json dict."""
    if limit:
        test_inputs = test_inputs.head(limit)
        print(f"[eval] --limit {limit}: scoring the first {len(test_inputs)} test inputs (partial run)")
    print(f"[eval] triaging {len(test_inputs)} tickets with skip_llm=True ...")
    preds = predict(test_inputs, triage_fn, progress_every=progress_every)
    pred_path = save_predictions(preds, out_dir)

    # Scoring step. test_labels.parquet is read here for the first time, after predictions are on disk.
    labels = load_labels(ddir)
    scores = score(pd.read_parquet(pred_path), labels)
    del labels

    metrics = build_metrics(scores, fingerprint, thresholds)
    write_outputs(metrics, render_md(metrics, scores, limit=limit, llm_sample=llm_sample), out_dir)
    c = metrics["classifier"]
    hpi = metrics["high_priority_incident"]
    print(
        "[eval] macro-F1 type={:.4f} queue={:.4f} priority={:.4f} | HPI support={} clf_recall={:.4f} "
        "esc_recall={:.4f} | escalation rate={:.4f} | errors={}".format(
            c["type"]["macro_f1"], c["queue"]["macro_f1"], c["priority"]["macro_f1"], hpi["support"],
            hpi["classifier_recall"], hpi["escalation_recall"], metrics["escalation"]["rate"], scores["n_errors"],
        )
    )
    return metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SentinelDesk holdout evaluation (A2.3)")
    ap.add_argument("--limit", type=int, default=None, help="score only the first N test inputs")
    ap.add_argument("--llm-sample", type=int, default=0, help="LLM sample size (task A2.5, not implemented yet)")
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
    if args.llm_sample > 0:
        print(f"[eval] NOTE: --llm-sample {args.llm_sample} is task A2.5 and is not implemented yet. "
              "Continuing with the skip_llm run only.")

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
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
