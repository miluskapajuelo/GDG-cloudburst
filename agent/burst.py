"""B1.6: live outage / burst detection (owner: Karanpatel3114).

Contract (docs/contract.md §2):
    BurstDetector(sim_threshold, min_cluster, window_minutes)
    .observe(request_id, vector, summary, ts=None) -> burst object as in the HTTP response
    .reset()

Rule: the cluster for a new ticket is the ticket itself plus every ticket still in the time
window that (a) has cosine similarity >= sim_threshold to it AND (b) shares at least one
*rare* term with it. The banner is active when the cluster has >= min_cluster tickets.

Why two signals: the dataset is templated, so unrelated tickets are already quite similar
(random KB pairs: p99 cosine 0.74). Cosine alone can't separate a real outage cluster from that
background. "Rare" means the term appears in < 2% of KB tickets. Product and symptom words like
"vpn" (0.28%) or "timeout" (0.18%) count; generic ones like "system" (17%) or "issue" (26%) don't.
agent.build_index writes the common-term list to artifacts/kb_common_terms.json. Measured on KB
samples (see agent/NOTES.md): at 0.65 + rare term, false-banner rate is 0% with 10 random tickets
in the window (cosine-only at 0.75: 4%), and the demo VPN burst still fires on the 3rd ticket.

Vectors come from Retriever.embed, so they are L2-normalised and the dot product is the cosine.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import Counter, deque
from pathlib import Path

import numpy as np

COMMON_TERMS_FILE = "kb_common_terms.json"
_MAX_WINDOW_ITEMS = 2000  # hard cap so a batch eval run can't grow the window without bound
_WORD_RE = re.compile(r"[^\W\d_][\w]{2,}", re.UNICODE)

# Fallback when artifacts/kb_common_terms.json is missing: plain function words only.
_STOPWORDS = frozenset({
    # en
    "the", "and", "for", "our", "are", "can", "not", "with", "since", "from", "this", "that", "all",
    "any", "has", "have", "was", "were", "been", "about", "into", "keeps", "today", "morning",
    "started", "around", "none", "staff", "please", "help", "hello", "team", "whole", "you", "your",
    "dear", "support", "issue", "problem", "system", "thanks", "thank", "regards", "since", "there",
    # de
    "der", "die", "das", "und", "mit", "von", "seit", "nicht", "mehr", "kein", "keine", "ist",
    "sind", "beim", "uhr", "ganze", "auf", "für", "bei", "wir", "ihr", "sie", "unser", "unsere",
    "sehr", "geehrte", "geehrtes", "damen", "herren", "bitte", "danke", "problem", "kunde",
})


def tokenize(text: str) -> list[str]:
    """Lower-cased word tokens (3+ chars, starting with a letter). Shared with build_index."""
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def load_common_terms(artifacts_dir: str | os.PathLike | None = None) -> frozenset[str]:
    base = Path(artifacts_dir or os.getenv("SENTINEL_ARTIFACTS_DIR", "artifacts"))
    path = base / COMMON_TERMS_FILE
    if path.exists():
        try:
            return frozenset(json.loads(path.read_text())) | _STOPWORDS
        except (OSError, ValueError):
            pass
    return _STOPWORDS


def _inactive(window_minutes: int) -> dict:
    return {"active": False, "cluster_size": 1, "window_minutes": window_minutes, "label": None, "request_ids": []}


def _label(summaries: list[str], rare_sets: list[set[str]]) -> str | None:
    """Short banner label, e.g. "VPN / timeout".

    1. Rare terms shared by most of the cluster, shown in their most common spelling.
    2. Otherwise the most common first 6 words, if any phrase repeats.
    3. Otherwise the earliest summary, truncated to 60 chars.
    """
    docs = [s for s in summaries if s and s.strip()]
    if not docs:
        return None

    df: Counter[str] = Counter()
    for rs in rare_sets:
        df.update(rs)
    need = max(2, int(np.ceil(0.6 * len(rare_sets))))
    shared = [w for w, c in df.most_common() if c >= need][:3]
    if shared:
        spelling: dict[str, Counter[str]] = {}
        for s in docs:
            for w in _WORD_RE.findall(s):
                spelling.setdefault(w.lower(), Counter())[w] += 1
        return " / ".join(spelling[w].most_common(1)[0][0] if w in spelling else w for w in shared)

    heads = Counter(" ".join(s.split()[:6]) for s in docs)
    phrase, count = heads.most_common(1)[0]
    if phrase and count >= 2:
        return phrase
    return docs[0].strip().replace("\n", " ")[:60]


class BurstDetector:
    def __init__(self, sim_threshold: float, min_cluster: int, window_minutes: int,
                 common_terms: set[str] | frozenset[str] | None = None):
        """common_terms is optional (not in the contract): by default it is loaded from
        $SENTINEL_ARTIFACTS_DIR/kb_common_terms.json, falling back to a built-in stopword list."""
        self.sim_threshold = float(sim_threshold)
        self.min_cluster = int(min_cluster)
        self.window_minutes = int(window_minutes)
        self._common = frozenset(common_terms) if common_terms is not None else load_common_terms()
        # (ts, request_id, unit vector, summary, rare terms)
        self._window: deque[tuple[float, str, np.ndarray, str, set[str]]] = deque(maxlen=_MAX_WINDOW_ITEMS)
        self._lock = threading.Lock()

    def rare_terms(self, text: str) -> set[str]:
        return {t for t in tokenize(text) if t not in self._common}

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_minutes * 60
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()

    def observe(self, request_id: str, vector: np.ndarray, summary: str, ts: float | None = None) -> dict:
        """Add the ticket to the window. Return the burst object as in the HTTP response."""
        now = time.time() if ts is None else float(ts)
        vec = np.asarray(vector, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        summary = summary or ""
        rare = self.rare_terms(summary)

        with self._lock:
            self._prune(now)
            members: list[tuple[float, str, str, set[str]]] = []
            if self._window and rare:
                sims = np.stack([item[2] for item in self._window]) @ vec
                members = [(item[0], item[1], item[3], item[4])
                           for item, s in zip(self._window, sims)
                           if s >= self.sim_threshold and (rare & item[4])]
            self._window.append((now, request_id, vec, summary, rare))

        if len(members) + 1 < self.min_cluster:
            return _inactive(self.window_minutes)
        cluster = sorted(members + [(now, request_id, summary, rare)], key=lambda m: m[0])
        return {
            "active": True,
            "cluster_size": len(cluster),
            "window_minutes": self.window_minutes,
            "label": _label([m[2] for m in cluster], [m[3] for m in cluster]),
            "request_ids": [m[1] for m in cluster],
        }

    def reset(self) -> None:
        with self._lock:
            self._window.clear()


if __name__ == "__main__":
    from sentence_transformers import SentenceTransformer

    m = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
    tickets = [
        "VPN down for whole office\n\nNone of our staff can connect to the corporate VPN since about 9:00. The client times out during the handshake.",
        "VPN-Verbindung bricht ab\n\nSeit ca. 9 Uhr kommt keine VPN-Verbindung mehr zustande, der Client bricht beim Verbindungsaufbau mit Timeout ab. Das ganze Team ist betroffen.",
        "VPN handshake timeout for all remote employees, started this morning around 9.",
        "Remote access not working\n\nOur remote workers can't reach internal systems, the VPN connection keeps timing out. Started today at 9am.",
        "Quick question\n\nCan you recommend a good recipe for a vegan chocolate cake and tell me tomorrow's weather in Berlin?",
    ]
    vecs = m.encode(tickets, normalize_embeddings=True)
    print("pairwise cosine:\n", np.round(vecs @ vecs.T, 2))
    d = BurstDetector(float(os.getenv("SENTINEL_BURST_SIM", "0.65")), 3, 15)
    for i, (t, v) in enumerate(zip(tickets, vecs)):
        print(i + 1, d.observe(f"req-{i + 1}", v, t[:120]))
