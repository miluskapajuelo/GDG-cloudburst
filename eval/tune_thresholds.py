"""Gate threshold tuning on KB validation rows only (A2.7, escalation-policy section 5).

Run from the repo root (needs data/kb_train.parquet, artifacts/val_preds.parquet and the B1 index):
    python -m eval.tune_thresholds
    python -m eval.tune_thresholds --limit 500        # quick partial run

What it does:
  1. Loads the KB validation rows (is_val == True) and A1's classifier probabilities for them
     (artifacts/val_preds.parquet). Never opens any test file.
  2. Per val ticket, once: mask PII, embed, Retriever.search(k=TOP_K, exclude_ids={ticket_id}) for the
     top-1 similarity, and the two threshold-free gate rules (PROMPT_INJECTION_SUSPECTED and
     UNSUPPORTED_REQUEST) from agent.gate.pre_draft_gate.
  3. Sweeps T_HIGH_PRIORITY_P, T_INCIDENT_P, T_CONF_TYPE/T_CONF_PRIORITY (tied), T_CONF_QUEUE and T_SIM.
     For each setting it reports HPI escalation recall, escalation rate and NO_PRECEDENT rate.
  4. Picks a recommended row by the policy targets, in priority order:
       HPI escalation recall >= 0.90, escalation rate in [0.30, 0.50], NO_PRECEDENT rate < 0.10.
  5. Sanity check: the out-of-scope demo ticket (demo-08) must fall below the recommended T_SIM.
  6. Writes eval/results/threshold_sweep.md and threshold_sweep.json. B2 copies the row into agent/config.py.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HEADS = ("type", "queue", "priority")
DEFAULTS: dict[str, float] = {
    "T_HIGH_PRIORITY_P": 0.35, "T_INCIDENT_P": 0.40, "T_CONF_TYPE": 0.45,
    "T_CONF_PRIORITY": 0.45, "T_CONF_QUEUE": 0.25, "T_SIM": 0.55,
}
TARGET_HPI_RECALL = 0.90
TARGET_RATE = (0.30, 0.50)
TARGET_NO_PRECEDENT = 0.10
DEFAULT_TOP_K = 5

GRID = {
    "T_HIGH_PRIORITY_P": [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50],
    "T_INCIDENT_P": [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55],
    "T_CONF_TP": [0.35, 0.40, 0.45, 0.50],  # T_CONF_TYPE and T_CONF_PRIORITY move together
    "T_CONF_QUEUE": [0.15, 0.20, 0.25, 0.30],
    # T_SIM: fixed points plus val similarity percentiles (added at run time)
    "T_SIM": [0.45, 0.50, 0.55, 0.60],
}
SIM_PERCENTILES = (2, 5, 10)
SIM_CACHE = "val_sims.parquet"


# ---------------------------------------------------------------- inputs

def data_dir() -> Path:
    return Path(os.getenv("SENTINEL_DATA_DIR", "data"))


def artifacts_dir() -> Path:
    return Path(os.getenv("SENTINEL_ARTIFACTS_DIR", "artifacts"))


def load_val(ddir: Path) -> pd.DataFrame:
    """KB validation rows only. Test files are never opened by this script."""
    path = ddir / "kb_train.parquet"
    assert "test" not in path.name
    kb = pd.read_parquet(path, columns=["ticket_id", "subject", "body", "type", "priority", "is_val"])
    val = kb[kb["is_val"].astype(bool)].drop(columns="is_val").reset_index(drop=True)
    assert len(val), "no validation rows (is_val == True) in kb_train.parquet"
    return val


def prob_columns(columns: Iterable[str], head: str) -> list[str]:
    """The '<head>__<label>' probability columns. Skips '<head>__true' (gold val label, a string column)."""
    return [c for c in columns if c.startswith(f"{head}__") and c != f"{head}__true"]


def load_val_probs(adir: Path) -> pd.DataFrame:
    """artifacts/val_preds.parquet: ticket_id plus one '<head>__<label>' column per class (A1.4).

    A1 also writes '<head>__true' (gold val label). It is ignored here; labels come from kb_train val rows.
    """
    probs = pd.read_parquet(adir / "val_preds.parquet")
    for head in HEADS:
        assert prob_columns(probs.columns, head), f"val_preds has no {head}__* probability columns"
    return probs


def classifier_features(probs: pd.DataFrame) -> pd.DataFrame:
    """Per ticket: P(priority=high), P(type=Incident) and the top-class confidence per head."""
    out = pd.DataFrame({"ticket_id": probs["ticket_id"].astype(str)})
    for head in HEADS:
        cols = prob_columns(probs.columns, head)
        out[f"conf_{head}"] = probs[cols].max(axis=1).to_numpy(dtype=float)
    out["p_high"] = probs.get("priority__high", pd.Series(0.0, index=probs.index)).to_numpy(dtype=float)
    out["p_incident"] = probs.get("type__Incident", pd.Series(0.0, index=probs.index)).to_numpy(dtype=float)
    return out


def predictions_from_row(row: pd.Series, probs_cols: dict[str, list[str]]) -> dict:
    """Contract-shaped predictions dict from one val_preds row (for agent.gate.pre_draft_gate)."""
    preds = {}
    for head, cols in probs_cols.items():
        p = {c.split("__", 1)[1]: float(row[c]) for c in cols}
        label = max(p, key=p.get)
        preds[head] = {"label": label, "confidence": p[label], "probs": p}
    return preds


# ---------------------------------------------------------------- per-ticket retrieval + fixed rules

def _load_agent() -> dict[str, Any]:
    """Real B1/B2 pieces where available. Missing pieces are reported, never faked."""
    parts: dict[str, Any] = {}
    from shared.text import build_text
    parts["build_text"] = build_text
    try:
        from agent.pii import mask_pii
        parts["mask_pii"] = mask_pii
    except ImportError as exc:
        print(f"[tune] agent.pii not available ({exc}); embedding unmasked text (local only, no LLM)")
        parts["mask_pii"] = lambda t: (t, {})
    try:
        from agent.gate import pre_draft_gate
        parts["pre_draft_gate"] = pre_draft_gate
    except ImportError as exc:
        print(f"[tune] agent.gate not available ({exc}); injection/unsupported rules counted as 0")
        parts["pre_draft_gate"] = None
    try:
        from agent import config as agent_config
        parts["top_k"] = int(getattr(agent_config, "TOP_K", DEFAULT_TOP_K))
    except ImportError:
        parts["top_k"] = DEFAULT_TOP_K
    from agent.retrieve import Retriever
    parts["retriever"] = Retriever.load(str(artifacts_dir()))
    return parts


def retrieval_features(
    val: pd.DataFrame,
    probs: pd.DataFrame,
    *,
    embed_search: Callable[[str, str], list[dict]],
    mask_pii: Callable[[str], tuple[str, dict]],
    build_text: Callable[[Any, Any], str],
    pre_draft_gate: Callable[[dict, list[dict], str], dict] | None,
    progress_every: int = 500,
) -> pd.DataFrame:
    """Per val ticket: top-1 similarity (self excluded) and the threshold-free rule flags.

    embed_search(text, ticket_id) must return precedents sorted by similarity, without ticket_id itself.
    """
    probs = probs.set_index(probs["ticket_id"].astype(str))
    probs_cols = {h: prob_columns(probs.columns, h) for h in HEADS}
    rows = []
    t0 = time.perf_counter()
    for i, (tid, subject, body) in enumerate(zip(val["ticket_id"], val["subject"], val["body"]), start=1):
        tid = str(tid)
        masked, _ = mask_pii(build_text(subject, body))
        precedents = embed_search(masked, tid)
        assert all(p.get("ticket_id") != tid for p in precedents), f"self-match not excluded for {tid}"
        top1 = float(precedents[0]["similarity"]) if precedents else 0.0
        injection = unsupported = False
        if pre_draft_gate is not None and tid in probs.index:
            codes = {r["code"] for r in pre_draft_gate(predictions_from_row(probs.loc[tid], probs_cols),
                                                       precedents, masked)["reasons"]}
            injection = "PROMPT_INJECTION_SUSPECTED" in codes
            unsupported = "UNSUPPORTED_REQUEST" in codes
        rows.append({"ticket_id": tid, "top1_sim": top1, "injection": injection, "unsupported": unsupported})
        if i % progress_every == 0 or i == len(val):
            print(f"[tune] retrieval {i}/{len(val)}  {time.perf_counter() - t0:.1f}s", flush=True)
    return pd.DataFrame(rows)


def build_features(val: pd.DataFrame, clf: pd.DataFrame, ret: pd.DataFrame) -> pd.DataFrame:
    """Join labels (val only), classifier features and retrieval features into one frame."""
    feats = (
        val[["ticket_id", "type", "priority"]].astype({"ticket_id": str})
        .merge(clf, on="ticket_id", how="inner", validate="one_to_one")
        .merge(ret, on="ticket_id", how="inner", validate="one_to_one")
    )
    missing = len(val) - len(feats)
    if missing:
        print(f"[tune] WARNING: {missing} val tickets have no classifier probabilities or retrieval result")
    feats["true_hpi"] = (feats["priority"] == "high") & (feats["type"] == "Incident")
    return feats


# ---------------------------------------------------------------- sweep

def sim_candidates(top1: Iterable[float]) -> list[float]:
    sims = np.asarray(list(top1), dtype=float)
    pts = set(GRID["T_SIM"])
    if len(sims):
        pts |= {round(float(np.percentile(sims, q)), 3) for q in SIM_PERCENTILES}
    return sorted(pts)


def evaluate(feats: pd.DataFrame, th: dict[str, float]) -> dict[str, Any]:
    """Gate outcome for one threshold setting (pre-draft rules only, as in skip_llm)."""
    hpi_rule = (feats["p_high"] >= th["T_HIGH_PRIORITY_P"]) & (feats["p_incident"] >= th["T_INCIDENT_P"])
    low_conf = ((feats["conf_type"] < th["T_CONF_TYPE"]) | (feats["conf_priority"] < th["T_CONF_PRIORITY"])
                | (feats["conf_queue"] < th["T_CONF_QUEUE"]))
    no_prec = feats["top1_sim"] < th["T_SIM"]
    esc = hpi_rule | low_conf | no_prec | feats["injection"] | feats["unsupported"]
    true_hpi = feats["true_hpi"]
    n, support = len(feats), int(true_hpi.sum())
    return {
        **{k: float(v) for k, v in th.items()},
        "hpi_escalation_recall": float((esc & true_hpi).sum() / support) if support else 0.0,
        "hpi_on_call_recall": float((hpi_rule & true_hpi).sum() / support) if support else 0.0,
        "escalation_rate": float(esc.mean()) if n else 0.0,
        "on_call_rate": float(hpi_rule.mean()) if n else 0.0,
        "low_conf_rate": float(low_conf.mean()) if n else 0.0,
        "no_precedent_rate": float(no_prec.mean()) if n else 0.0,
    }


def sweep(feats: pd.DataFrame, grid: dict[str, list[float]] | None = None) -> pd.DataFrame:
    """Every combination of the grid, vectorised over tickets. Returns one row per setting."""
    grid = dict(grid or GRID)
    grid["T_SIM"] = sorted(set(grid["T_SIM"]) | set(sim_candidates(feats["top1_sim"])))
    keys = ("T_HIGH_PRIORITY_P", "T_INCIDENT_P", "T_CONF_TP", "T_CONF_QUEUE", "T_SIM")
    rows = []
    for hp, inc, tp, q, sim in itertools.product(*(grid[k] for k in keys)):
        th = {"T_HIGH_PRIORITY_P": hp, "T_INCIDENT_P": inc, "T_CONF_TYPE": tp, "T_CONF_PRIORITY": tp,
              "T_CONF_QUEUE": q, "T_SIM": sim}
        rows.append(evaluate(feats, th))
    return pd.DataFrame(rows)


def _distance_to_defaults(df: pd.DataFrame) -> pd.Series:
    return sum((df[k] - v).abs() for k, v in DEFAULTS.items())


def recommend(results: pd.DataFrame) -> tuple[pd.Series, str]:
    """Pick one row by the policy targets in priority order. Relax the lowest-priority target first."""
    recall_ok = results["hpi_escalation_recall"] >= TARGET_HPI_RECALL
    rate_ok = results["escalation_rate"].between(*TARGET_RATE)
    np_ok = results["no_precedent_rate"] < TARGET_NO_PRECEDENT
    tiers = [
        (recall_ok & rate_ok & np_ok, "all three targets met"),
        (recall_ok & rate_ok, "NO_PRECEDENT target relaxed (no setting met all three)"),
        (recall_ok, "escalation-rate and NO_PRECEDENT targets relaxed"),
        (pd.Series(True, index=results.index), "no setting reaches HPI recall 0.90: best recall shown"),
    ]
    for mask, note in tiers:
        cand = results[mask].copy()
        if cand.empty:
            continue
        # Inside the feasible set: highest HPI escalation recall (the metric the brief singles out), then
        # the lowest escalation rate (the gate must stay useful), then the fewest changes from the defaults.
        cand["_k1"] = -cand["hpi_escalation_recall"].round(4)
        cand["_k2"] = cand["escalation_rate"].round(4)
        cand["_k3"] = _distance_to_defaults(cand)
        best = cand.sort_values(["_k1", "_k2", "_k3"]).iloc[0]
        return best.drop(["_k1", "_k2", "_k3"]), note
    raise ValueError("empty sweep")


# ---------------------------------------------------------------- report

def _fmt(v: Any) -> str:
    return f"{v:.4f}" if isinstance(v, float) else str(v)


def _table(header: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_fmt(c) for c in r) + " |" for r in rows]
    return out + [""]


TH_COLS = ["T_HIGH_PRIORITY_P", "T_INCIDENT_P", "T_CONF_TYPE", "T_CONF_PRIORITY", "T_CONF_QUEUE", "T_SIM"]
METRIC_COLS = ["hpi_escalation_recall", "escalation_rate", "no_precedent_rate", "hpi_on_call_recall",
               "on_call_rate", "low_conf_rate"]


def render_md(feats: pd.DataFrame, results: pd.DataFrame, best: pd.Series, note: str,
              defaults_row: dict[str, Any], sanity: dict[str, Any] | None, *, limit: int | None) -> str:
    sims = feats["top1_sim"]
    lines = [
        "# Gate threshold sweep (KB validation rows only)",
        "",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Val tickets: {len(feats)}" + (f" (PARTIAL RUN: --limit {limit})" if limit else ""),
        f"- True high-priority Incidents in val: {int(feats['true_hpi'].sum())}",
        f"- Settings evaluated: {len(results)}",
        "- Pre-draft rules only (as with skip_llm). Retrieval excludes each ticket's own KB row.",
        f"- Threshold-free rules: PROMPT_INJECTION_SUSPECTED on {int(feats['injection'].sum())} tickets,"
        f" UNSUPPORTED_REQUEST on {int(feats['unsupported'].sum())} ({feats['unsupported'].mean():.4f}).",
        "- Targets (escalation-policy section 5): HPI escalation recall >= 0.90, escalation rate 0.30-0.50,"
        " NO_PRECEDENT < 0.10.",
        "",
        "## Recommended row",
        "",
        f"Selection: {note}. Within the feasible set the highest HPI escalation recall wins, then the lowest"
        " escalation rate, then the fewest changes from the current defaults.",
        "",
    ]
    lines += _table(["Threshold", "Current default", "Recommended"],
                    [[k, DEFAULTS[k], float(best[k])] for k in TH_COLS])
    lines += _table(["Metric", "Current defaults", "Recommended"],
                    [[m, defaults_row[m], float(best[m])] for m in METRIC_COLS])
    lines += ["For `agent/config.py` (B2, prithvipoojari):", "", "```python"]
    lines += [f"{k} = {float(best[k]):g}" for k in TH_COLS]
    lines += ["```", ""]

    if sanity is not None:
        verdict = "PASS" if sanity["below"] else "FAIL"
        lines += ["## Sanity check: out-of-scope ticket demo-08", "",
                  f"Top-1 similarity {sanity['top1_sim']:.4f} vs recommended T_SIM {float(best['T_SIM']):g}:"
                  f" **{verdict}** (must be below, so it escalates with NO_PRECEDENT).", ""]

    lines += ["## Val top-1 similarity distribution", ""]
    lines += _table(["p1", "p2", "p5", "p10", "p25", "p50"],
                    [[round(float(np.percentile(sims, q)), 4) for q in (1, 2, 5, 10, 25, 50)]])

    lines += ["## One threshold at a time (others at the recommended row)", ""]
    for k in TH_COLS:
        key = "T_CONF_TYPE" if k == "T_CONF_PRIORITY" else k
        if k == "T_CONF_PRIORITY":
            continue
        mask = pd.Series(True, index=results.index)
        for other in TH_COLS:
            if other == key or (key == "T_CONF_TYPE" and other == "T_CONF_PRIORITY"):
                continue
            mask &= np.isclose(results[other], float(best[other]))
        sub = results[mask].sort_values(key)
        title = "T_CONF_TYPE = T_CONF_PRIORITY" if key == "T_CONF_TYPE" else key
        lines += [f"### {title}", ""]
        lines += _table([key, "HPI esc recall", "Esc rate", "NO_PRECEDENT", "ON_CALL rate"],
                        [[float(r[key]), r["hpi_escalation_recall"], r["escalation_rate"],
                          r["no_precedent_rate"], r["on_call_rate"]] for _, r in sub.iterrows()])

    ok = results[(results["hpi_escalation_recall"] >= TARGET_HPI_RECALL)
                 & results["escalation_rate"].between(*TARGET_RATE)
                 & (results["no_precedent_rate"] < TARGET_NO_PRECEDENT)]
    lines += [f"## Settings meeting all three targets: {len(ok)} (highest HPI recall first, top 15)", ""]
    if len(ok):
        top = ok.sort_values(["hpi_escalation_recall", "escalation_rate"], ascending=[False, True]).head(15)
        lines += _table(TH_COLS + ["HPI esc recall", "Esc rate", "NO_PRECEDENT"],
                        [[float(r[c]) for c in TH_COLS] + [r["hpi_escalation_recall"], r["escalation_rate"],
                                                          r["no_precedent_rate"]] for _, r in top.iterrows()])
    return "\n".join(lines)


# ---------------------------------------------------------------- orchestration

def demo08_text() -> str | None:
    path = Path("shared/fixtures/demo_tickets.json")
    try:
        tickets = json.loads(path.read_text(encoding="utf-8"))["tickets"]
    except (OSError, ValueError, KeyError):
        return None
    t = next((t for t in tickets if t.get("id") == "demo-08"), None)
    return None if t is None else f"{t.get('subject') or ''}\n\n{t.get('body') or ''}".strip()


def run(feats: pd.DataFrame, out_dir: Path, *, demo08_sim: float | None, limit: int | None = None,
        grid: dict[str, list[float]] | None = None) -> dict[str, Any]:
    results = sweep(feats, grid)
    best, note = recommend(results)
    defaults_row = evaluate(feats, DEFAULTS)
    sanity = None if demo08_sim is None else {"top1_sim": demo08_sim, "below": demo08_sim < float(best["T_SIM"])}
    out_dir.mkdir(parents=True, exist_ok=True)
    md = render_md(feats, results, best, note, defaults_row, sanity, limit=limit)
    (out_dir / "threshold_sweep.md").write_text(md + "\n", encoding="utf-8")
    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_val": int(len(feats)),
        "n_val_hpi": int(feats["true_hpi"].sum()),
        "selection": note,
        "recommended": {k: float(best[k]) for k in TH_COLS},
        "recommended_metrics": {m: round(float(best[m]), 4) for m in METRIC_COLS},
        "defaults": dict(DEFAULTS),
        "defaults_metrics": {m: round(float(defaults_row[m]), 4) for m in METRIC_COLS},
        "demo08_sanity": sanity,
    }
    (out_dir / "threshold_sweep.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"[tune] wrote {out_dir / 'threshold_sweep.md'} and threshold_sweep.json")
    r = summary["recommended_metrics"]
    print(f"[tune] recommended ({note}): " + ", ".join(f"{k}={v:g}" for k, v in summary["recommended"].items()))
    print(f"[tune]   HPI esc recall={r['hpi_escalation_recall']:.4f}  esc rate={r['escalation_rate']:.4f}  "
          f"NO_PRECEDENT={r['no_precedent_rate']:.4f}")
    if sanity is not None and not sanity["below"]:
        print("[tune] WARNING: demo-08 is NOT below the recommended T_SIM")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SentinelDesk gate threshold sweep on KB val (A2.7)")
    ap.add_argument("--limit", type=int, default=None, help="use only the first N val tickets")
    ap.add_argument("--out", type=Path, default=Path("eval/results"), help="output folder")
    ap.add_argument("--refresh", action="store_true", help=f"ignore the cached artifacts/{SIM_CACHE}")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    val = load_val(data_dir())
    if args.limit:
        val = val.head(args.limit)
    probs = load_val_probs(artifacts_dir())
    clf = classifier_features(probs)
    print(f"[tune] val tickets: {len(val)}  with classifier probs: {int(val['ticket_id'].isin(clf['ticket_id']).sum())}")

    parts = _load_agent()
    retriever = parts["retriever"]
    top_k = parts["top_k"]

    def embed_search(text: str, tid: str) -> list[dict]:
        return retriever.search(retriever.embed(text), k=top_k, exclude_ids={tid})

    cache = artifacts_dir() / SIM_CACHE
    ret = None
    if cache.exists() and not args.refresh:
        cached = pd.read_parquet(cache)
        if set(val["ticket_id"].astype(str)) <= set(cached["ticket_id"]):
            ret = cached[cached["ticket_id"].isin(val["ticket_id"].astype(str))]
            print(f"[tune] using cached retrieval features from {cache} (pass --refresh to recompute)")
    if ret is None:
        ret = retrieval_features(val, probs, embed_search=embed_search, mask_pii=parts["mask_pii"],
                                 build_text=parts["build_text"], pre_draft_gate=parts["pre_draft_gate"])
        if not args.limit:
            ret.to_parquet(cache, index=False)

    demo08_sim = None
    text = demo08_text()
    if text:
        masked, _ = parts["mask_pii"](text)
        hits = embed_search(masked, "")
        demo08_sim = float(hits[0]["similarity"]) if hits else 0.0

    run(build_features(val, clf, ret), args.out, demo08_sim=demo08_sim, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
