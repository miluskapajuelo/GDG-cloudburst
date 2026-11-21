"""Inference wrapper for the triage classifier (contract §2, A1).

Run the smoke test: python -m ml.predict
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import joblib

HEADS = ("type", "queue", "priority")


class TriageClassifier:
    def __init__(self, bundle: dict[str, Any]) -> None:
        self.vectorizer = bundle["vectorizer"]
        self.heads = bundle["heads"]
        self.labels: dict[str, list[str]] = bundle["labels"]
        self.version: str = bundle.get("version", "unknown")
        self.trained_on: str = bundle.get("trained_on", "unknown")

    @classmethod
    def load(cls, path: str = "artifacts/clf.joblib") -> "TriageClassifier":
        return cls(joblib.load(Path(path)))

    def predict(self, text: str) -> dict:
        """Return {"type": Pred, "queue": Pred, "priority": Pred}
        where Pred = {"label": str, "confidence": float, "probs": dict[str, float]}."""
        X = self.vectorizer.transform([text or ""])
        out: dict[str, dict] = {}
        for h in HEADS:
            model = self.heads[h]
            p = model.predict_proba(X)[0]
            total = float(p.sum()) or 1.0
            probs = {str(c): float(v) / total for c, v in zip(model.classes_, p)}
            label = max(probs, key=probs.__getitem__)
            out[h] = {"label": label, "confidence": probs[label], "probs": probs}
        return out


if __name__ == "__main__":
    from shared.text import build_text

    clf = TriageClassifier.load()
    samples = [
        ("VPN down for the whole office", "Since 8am nobody can connect to the VPN. Production work is blocked, please help urgently."),
        ("Rechnung doppelt abgebucht", "Guten Tag, mir wurde die Rechnung für November zweimal abgebucht. Bitte erstatten Sie den Betrag."),
        (None, "Could you tell me whether your product integrates with our CRM? We are evaluating options for next quarter."),
    ]
    for subject, body in samples:
        pred = clf.predict(build_text(subject, body))
        for h in HEADS:
            p = pred[h]
            assert p["label"] in clf.labels[h]
            assert isinstance(p["confidence"], float) and all(type(v) is float for v in p["probs"].values())
            assert abs(sum(p["probs"].values()) - 1.0) < 0.01
            assert p["confidence"] == max(p["probs"].values()) == p["probs"][p["label"]]
        print(f"{(subject or '<no subject>')[:32]:<34}", {h: (pred[h]["label"], round(pred[h]["confidence"], 2)) for h in HEADS})

    text = build_text(*samples[0])
    clf.predict(text)
    n = 200
    t = time.perf_counter()
    for _ in range(n):
        clf.predict(text)
    ms = (time.perf_counter() - t) * 1000 / n
    print(f"predict latency: {ms:.1f} ms/ticket")
    assert ms < 20, "predict slower than 20 ms"
    print("ml.predict OK")
