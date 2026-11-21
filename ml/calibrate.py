"""A1.6 experiments on KB val only: ECE per head, sigmoid calibration, C sweep.

Run: python -m ml.calibrate      (never reads test files)
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import f1_score

from ml.train import HEADS, make_head, make_vectorizer
from shared.text import build_text

DATA = Path("data")


def ece(probs: np.ndarray, classes: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    """Top-label expected calibration error with equal-width bins."""
    conf = probs.max(axis=1)
    correct = classes[probs.argmax(axis=1)] == y
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(total)


def evaluate(model, X_val, y: np.ndarray) -> tuple[float, float]:
    P = model.predict_proba(X_val)
    pred = model.classes_[P.argmax(axis=1)]
    return f1_score(y, pred, average="macro"), ece(P, model.classes_, y)


def main() -> None:
    kb = pd.read_parquet(DATA / "kb_train.parquet")
    kb["text"] = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]
    fit, val = kb[~kb["is_val"]], kb[kb["is_val"]]
    vec = make_vectorizer()
    X_fit, X_val = vec.fit_transform(fit["text"]), vec.transform(val["text"])

    rows = []
    for h in HEADS:
        y_fit, y_val = fit[h].to_numpy(), val[h].to_numpy()
        for C in (1.0, 4.0, 10.0):
            t = time.perf_counter()
            f1, e = evaluate(make_head(C).fit(X_fit, y_fit), X_val, y_val)
            rows.append({"head": h, "model": f"LR C={C:g}", "macro_f1": f1, "ece": e, "s": time.perf_counter() - t})
            print(rows[-1], flush=True)
        t = time.perf_counter()
        cal = CalibratedClassifierCV(make_head(4.0), method="sigmoid", cv=3).fit(X_fit, y_fit)
        f1, e = evaluate(cal, X_val, y_val)
        rows.append({"head": h, "model": "LR C=4 + sigmoid cv=3", "macro_f1": f1, "ece": e, "s": time.perf_counter() - t})
        print(rows[-1], flush=True)

    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False, float_format="%.4f"))


if __name__ == "__main__":
    main()
