#!/usr/bin/env python3
"""
Holdout Evaluation Script
Owner: A2 (Gustavo)

Runs evaluation on the test (holdout) set and computes metrics.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api import service


def compute_split_fingerprint(test_df: pd.DataFrame) -> str:
    """Compute split fingerprint as per data-and-leakage.md."""
    ticket_ids = "".join(sorted(test_df["ticket_id"].tolist()))
    return hashlib.sha256(ticket_ids.encode()).hexdigest()[:12]


def check_leakage_asserts(kb_df: pd.DataFrame, test_inputs_df: pd.DataFrame):
    """Re-check leakage asserts from data-and-leakage.md."""
    # Assert no answer column in test
    assert "answer" not in test_inputs_df.columns, "test_inputs should not have answer column!"
    
    # Assert no overlap in ticket IDs
    kb_ids = set(kb_df["ticket_id"])
    test_ids = set(test_inputs_df["ticket_id"])
    overlap = kb_ids.intersection(test_ids)
    assert len(overlap) == 0, f"KB and test have overlapping ticket IDs: {overlap}"
    
    print("✅ Leakage asserts passed")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all data splits."""
    data_dir = Path("data")
    
    kb_train = pd.read_parquet(data_dir / "kb_train.parquet")
    test_inputs = pd.read_parquet(data_dir / "test_inputs.parquet")
    
    # Check if test_labels exists (only for scoring step)
    test_labels_path = data_dir / "test_labels.parquet"
    if test_labels_path.exists():
        test_labels = pd.read_parquet(test_labels_path)
    else:
        test_labels = None
    
    return kb_train, test_inputs, test_labels


def run_triage_for_row(row: pd.Series, skip_llm: bool = True) -> Dict[str, Any]:
    """Run triage for a single row."""
    subject = row.get("subject", "") or ""
    body = row.get("body", "") or ""
    
    try:
        result = service.triage(subject, body, skip_llm=skip_llm)
        return result
    except Exception as e:
        print(f"Error processing {row.get('ticket_id', 'unknown')}: {e}")
        return {
            "request_id": "",
            "predictions": {"type": {}, "queue": {}, "priority": {}},
            "escalation": {"status": "ERROR", "route": None, "reasons": []},
            "language": {"code": "en"},
            "latency_ms": {"total": 0}
        }


def score_predictions(
    predictions_df: pd.DataFrame, 
    labels_df: pd.DataFrame
) -> Dict[str, Any]:
    """Compute metrics against ground truth labels."""
    from sklearn.metrics import f1_score, accuracy_score, confusion_matrix, classification_report
    
    # Merge predictions with labels
    merged = predictions_df.merge(labels_df, on="ticket_id")
    
    metrics = {}
    
    # Per-head metrics
    for head in ["type", "queue", "priority"]:
        pred_col = f"pred_{head}"
        true_col = head
        
        y_true = merged[true_col].values
        y_pred = merged[pred_col].values
        
        # Get all unique labels from both
        all_labels = sorted(set(y_true) | set(y_pred))
        
        macro_f1 = f1_score(y_true, y_pred, average="macro", labels=all_labels, zero_division=0)
        weighted_f1 = f1_score(y_true, y_pred, average="weighted", labels=all_labels, zero_division=0)
        acc = accuracy_score(y_true, y_pred)
        
        metrics[head] = {
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "accuracy": round(acc, 4)
        }
    
    # High-Priority Incident metrics
    merged["is_hpi_true"] = (merged["priority"] == "high") & (merged["type"] == "Incident")
    merged["is_hpi_pred"] = (merged["pred_priority"] == "high") & (merged["pred_type"] == "Incident")
    merged["is_escalated"] = merged["escalation_status"] == "ESCALATE"
    
    hpi_true_count = merged["is_hpi_true"].sum()
    
    if hpi_true_count > 0:
        hpi_recall = merged["is_hpi_pred"].sum() / hpi_true_count
        escalation_recall = merged[merged["is_hpi_true"]]["is_escalated"].sum() / hpi_true_count
    else:
        hpi_recall = 0.0
        escalation_recall = 0.0
    
    metrics["high_priority_incident"] = {
        "support": int(hpi_true_count),
        "classifier_recall": round(hpi_recall, 4),
        "escalation_recall": round(escalation_recall, 4)
    }
    
    # Escalation metrics
    total = len(merged)
    escalation_rate = merged["is_escalated"].sum() / total if total > 0 else 0
    
    reason_counts = merged["escalation_reason"].value_counts().to_dict()
    
    metrics["escalation"] = {
        "rate": round(escalation_rate, 4),
        "reason_counts": reason_counts
    }
    
    # Language detection accuracy
    lang_acc = (merged["pred_language"] == merged["language"]).mean()
    metrics["language_detection_accuracy"] = round(lang_acc, 4)
    
    return metrics


def compute_latency_stats(predictions_df: pd.DataFrame) -> Dict[str, Any]:
    """Compute latency statistics."""
    latency_cols = ["latency_pii", "latency_language", "latency_classify", 
                   "latency_retrieve", "latency_gate", "latency_total"]
    
    result = {"skip_llm": {}, "with_llm": {}}
    
    for col in latency_cols:
        if col in predictions_df.columns:
            vals = predictions_df[col].dropna()
            if len(vals) > 0:
                result["skip_llm"][col.replace("latency_", "")] = {
                    "p50": int(np.percentile(vals, 50)),
                    "p95": int(np.percentile(vals, 95)),
                    "n": len(vals)
                }
    
    return result


def write_metrics(metrics: Dict, output_dir: Path):
    """Write metrics to JSON and MD files."""
    # JSON
    metrics_json_path = output_dir / "metrics.json"
    with open(metrics_json_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"✅ Written {metrics_json_path}")
    
    # Markdown
    metrics_md_path = output_dir / "metrics.md"
    with open(metrics_md_path, "w") as f:
        f.write("# Evaluation Metrics\n\n")
        
        f.write("## Classifier Performance\n\n")
        for head in ["type", "queue", "priority"]:
            m = metrics.get(head, {})
            f.write(f"### {head.capitalize()}\n")
            f.write(f"- Macro-F1: {m.get('macro_f1', 0):.4f}\n")
            f.write(f"- Weighted-F1: {m.get('weighted_f1', 0):.4f}\n")
            f.write(f"- Accuracy: {m.get('accuracy', 0):.4f}\n\n")
        
        f.write("## High-Priority Incident\n\n")
        hpi = metrics.get("high_priority_incident", {})
        f.write(f"- Support (count): {hpi.get('support', 0)}\n")
        f.write(f"- Classifier Recall: {hpi.get('classifier_recall', 0):.4f}\n")
        f.write(f"- Escalation Recall: {hpi.get('escalation_recall', 0):.4f}\n\n")
        
        f.write("## Escalation\n\n")
        esc = metrics.get("escalation", {})
        f.write(f"- Escalation Rate: {esc.get('rate', 0):.2%}\n")
        f.write(f"- Reason Counts: {esc.get('reason_counts', {})}\n\n")
        
        f.write("## Language Detection\n\n")
        f.write(f"- Accuracy: {metrics.get('language_detection_accuracy', 0):.4f}\n\n")
        
        f.write("## Latency (ms)\n\n")
        lat = metrics.get("latency_ms", {}).get("skip_llm", {})
        for stage, stats in lat.items():
            f.write(f"- {stage}: p50={stats.get('p50', 0)}, p95={stats.get('p95', 0)}\n")
    
    print(f"✅ Written {metrics_md_path}")


def main():
    parser = argparse.ArgumentParser(description="Run holdout evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test samples")
    parser.add_argument("--llm-sample", type=int, default=0, help="Run LLM on N samples")
    parser.add_argument("--out", type=str, default="eval/results", help="Output directory")
    args = parser.parse_args()
    
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("📊 Loading data...")
    kb_train, test_inputs, test_labels = load_data()
    
    print(f"KB: {len(kb_train)} rows")
    print(f"Test inputs: {len(test_inputs)} rows")
    if test_labels is not None:
        print(f"Test labels: {len(test_labels)} rows")
    
    # Check leakage
    print("🔒 Checking leakage...")
    check_leakage_asserts(kb_train, test_inputs)
    
    # Compute fingerprint
    fingerprint = compute_split_fingerprint(test_inputs)
    print(f"Fingerprint: {fingerprint}")
    
    # Limit if specified
    if args.limit:
        test_inputs = test_inputs.head(args.limit)
        print(f"Limited to {args.limit} samples")
    
    # Load models if not in mock mode
    if os.getenv("SENTINEL_MOCK", "0") != "1":
        print("📦 Loading models...")
        try:
            service.load_classifier()
            service.load_retriever()
            service.init_burst_detector()
            service.init_pipeline()
        except Exception as e:
            print(f"⚠️  Model loading failed: {e}")
            print("Running in fallback mode...")
    
    # Run triage on test inputs (skip_llm=True for main eval)
    print("🏃 Running triage on test set...")
    results = []
    
    for idx, row in tqdm(test_inputs.iterrows(), total=len(test_inputs), desc="Triage"):
        result = run_triage_for_row(row, skip_llm=True)
        
        # Extract key fields for scoring
        pred_row = {
            "ticket_id": row["ticket_id"],
            "pred_type": result.get("predictions", {}).get("type", {}).get("label", ""),
            "pred_queue": result.get("predictions", {}).get("queue", {}).get("label", ""),
            "pred_priority": result.get("predictions", {}).get("priority", {}).get("label", ""),
            "pred_language": result.get("language", {}).get("code", "en"),
            "escalation_status": result.get("escalation", {}).get("status", "AUTO_DRAFT"),
            "escalation_reason": result.get("escalation", {}).get("reasons", [{}])[0].get("code", "NONE") if result.get("escalation", {}).get("reasons") else "NONE",
            "latency_pii": result.get("latency_ms", {}).get("pii", 0),
            "latency_language": result.get("latency_ms", {}).get("language", 0),
            "latency_classify": result.get("latency_ms", {}).get("classify", 0),
            "latency_retrieve": result.get("latency_ms", {}).get("retrieve", 0),
            "latency_gate": result.get("latency_ms", {}).get("gate", 0),
            "latency_total": result.get("latency_ms", {}).get("total", 0),
        }
        results.append(pred_row)
    
    predictions_df = pd.DataFrame(results)
    
    # Save predictions
    predictions_path = output_dir / "test_predictions.parquet"
    predictions_df.to_parquet(predictions_path)
    print(f"✅ Saved predictions to {predictions_path}")
    
    # Score if labels available
    metrics = {
        "generated_at": datetime.now().isoformat() + "Z",
        "split_fingerprint": fingerprint,
        "n_test": len(test_inputs),
    }
    
    if test_labels is not None:
        print("📈 Computing metrics...")
        score_metrics = score_predictions(predictions_df, test_labels)
        metrics.update(score_metrics)
        
        # Latency stats
        metrics["latency_ms"] = compute_latency_stats(predictions_df)
    else:
        print("⚠️  No test labels - cannot compute metrics")
    
    # Write metrics
    write_metrics(metrics, output_dir)
    
    print("✅ Evaluation complete!")


if __name__ == "__main__":
    from datetime import datetime
    main()