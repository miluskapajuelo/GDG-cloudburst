"""Train the TF-IDF + logistic regression triage classifier (A1.4).

Trains on KB rows with is_val == False, evaluates on the KB val slice, and writes:
  artifacts/clf.joblib        bundle {"vectorizer", "heads", "labels", "trained_on", "version"}
  artifacts/labels.json       label lists per head
  artifacts/val_preds.parquet ticket_id, then per head: one column "<head>__<label>" per class
                              (probability) and "<head>__true" (gold val label). For A2 threshold tuning.

Never reads test files.

Run: python -m ml.train
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion

from shared.text import build_text

DATA = Path("data")
ARTIFACTS = Path("artifacts")
HEADS = ("type", "queue", "priority")
VERSION = "tfidf-lr-v1"


def make_vectorizer() -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=200_000
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, max_features=300_000
                ),
            ),
        ]
    )


def make_head(C: float = 4.0) -> OneVsRestClassifier:
    # sklearn >= 1.8 dropped implicit OvR for liblinear, so wrap it explicitly.
    # (saga multinomial took > 10 min on ~140k sparse features; liblinear OvR takes seconds.)
    return OneVsRestClassifier(
        LogisticRegression(class_weight="balanced", max_iter=2000, C=C, solver="liblinear")
    )


def hpi_recall(y_type: np.ndarray, y_prio: np.ndarray, p_type: np.ndarray, p_prio: np.ndarray) -> tuple[float, int]:
    """Recall of (high, Incident): predicted high AND Incident among true high Incidents."""
    true_hpi = (y_type == "Incident") & (y_prio == "high")
    pred_hpi = (p_type == "Incident") & (p_prio == "high")
    n = int(true_hpi.sum())
    return (float((pred_hpi & true_hpi).sum() / n) if n else 0.0), n


def _fit_head(X, y: np.ndarray) -> OneVsRestClassifier:
    return make_head().fit(X, y)


def main() -> None:
    t0 = time.perf_counter()
    kb = pd.read_parquet(DATA / "kb_train.parquet")
    texts = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]
    kb = kb.assign(text=texts)
    fit = kb[~kb["is_val"]].reset_index(drop=True)
    val = kb[kb["is_val"]].reset_index(drop=True)
    print(f"fit rows={len(fit)}  val rows={len(val)}")

    vec = make_vectorizer()
    X_fit = vec.fit_transform(fit["text"])
    X_val = vec.transform(val["text"])
    print(f"features={X_fit.shape[1]}  vectorize {time.perf_counter() - t0:.1f}s")

    t1 = time.perf_counter()
    # Sequential on purpose: liblinear segfaults under threads and loky memmaps break it.
    heads = {h: _fit_head(X_fit, fit[h].to_numpy()) for h in HEADS}
    print(f"heads trained in {time.perf_counter() - t1:.1f}s")

    labels = {h: [str(c) for c in heads[h].classes_] for h in HEADS}
    preds: dict[str, np.ndarray] = {}
    val_out = pd.DataFrame({"ticket_id": val["ticket_id"]})
    print("\nVal metrics")
    print(f"{'head':<10}{'macro_f1':>10}{'accuracy':>10}")
    for h in HEADS:
        P = heads[h].predict_proba(X_val)
        pred = heads[h].classes_[P.argmax(axis=1)]
        preds[h] = pred
        y = val[h].to_numpy()
        print(f"{h:<10}{f1_score(y, pred, average='macro'):>10.4f}{accuracy_score(y, pred):>10.4f}")
        for j, lab in enumerate(labels[h]):
            val_out[f"{h}__{lab}"] = P[:, j]
        val_out[f"{h}__true"] = y

    rec, n = hpi_recall(val["type"].to_numpy(), val["priority"].to_numpy(), preds["type"], preds["priority"])
    print(f"\nval HPI recall (pred high & Incident | true high & Incident): {rec:.4f}  (n={n})")

    ARTIFACTS.mkdir(exist_ok=True)
    bundle = {
        "vectorizer": vec,
        "heads": heads,
        "labels": labels,
        "trained_on": "kb_fit",
        "version": VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    joblib.dump(bundle, ARTIFACTS / "clf.joblib", compress=3)
    (ARTIFACTS / "labels.json").write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    val_out.to_parquet(ARTIFACTS / "val_preds.parquet", index=False)
    print(f"\nwrote {ARTIFACTS / 'clf.joblib'}, labels.json, val_preds.parquet  total {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
