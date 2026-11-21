"""B1.4: top-k retrieval of past KB tickets (owner: Karanpatel3114).

Contract (docs/contract.md §2):
    Retriever.load(index_dir="artifacts") -> Retriever
    Retriever.size -> int
    Retriever.embed(text) -> np.ndarray, shape (384,), float32, L2-normalised
    Retriever.search(vector, k=5, exclude_ids=None) -> list[precedent dict], similarity descending

Smoke test:  python -m agent.retrieve
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# IMPORT ORDER MATTERS (macOS segfault otherwise): torch, via sentence-transformers, must load
# before faiss, and faiss must run single-threaded. Each ships its own OpenMP runtime, and they
# crash during CPU encoding. Single-threaded flat search over ~23k vectors still takes ~1 ms.
from sentence_transformers import SentenceTransformer  # noqa: I001  (must precede faiss)
import faiss  # noqa: E402

faiss.omp_set_num_threads(1)

DEFAULT_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
ANSWER_SNIPPET_CHARS = 400


def _as_list(tags) -> list[str]:
    if tags is None or isinstance(tags, float):
        return []
    return [str(t) for t in list(tags)]


class Retriever:
    def __init__(self, index: faiss.Index, meta: pd.DataFrame, model, model_name: str):
        self._index = index
        self._model = model
        self.model_name = model_name
        # Pre-build plain-Python rows once so search() does no pandas work per request.
        self._rows: list[dict] = [
            {
                "ticket_id": str(r.ticket_id),
                "language": str(r.language),
                "subject": str(r.subject or ""),
                "body_snippet": str(r.body_snippet or ""),
                "answer_snippet": str(r.answer or "")[:ANSWER_SNIPPET_CHARS],
                "answer": str(r.answer or ""),
                "type": str(r.type),
                "queue": str(r.queue),
                "priority": str(r.priority),
                "tags": _as_list(r.tags),
            }
            for r in meta.itertuples(index=False)
        ]
        if len(self._rows) != index.ntotal:
            raise ValueError(f"kb_meta has {len(self._rows)} rows but the index has {index.ntotal}")

    @classmethod
    def load(cls, index_dir: str = "artifacts") -> "Retriever":
        load_dotenv()
        base = Path(os.getenv("SENTINEL_ARTIFACTS_DIR", index_dir) if index_dir == "artifacts" else index_dir)
        index = faiss.read_index(str(base / "kb.faiss"))
        meta = pd.read_parquet(base / "kb_meta.parquet")

        # Query with the same model that built the index.
        info_path = base / "kb_index_info.json"
        model_name = os.getenv("SENTINEL_EMBED_MODEL", DEFAULT_EMBED_MODEL)
        max_seq = 256
        if info_path.exists():
            info = json.loads(info_path.read_text())
            model_name = info.get("embed_model", model_name)
            max_seq = info.get("max_seq_length", max_seq)

        # Single-query encoding is fastest on CPU (MPS/CUDA launch overhead dominates for 1 text).
        model = SentenceTransformer(model_name, device=os.getenv("SENTINEL_EMBED_DEVICE", "cpu"))
        model.max_seq_length = max_seq
        return cls(index, meta, model, model_name)

    @property
    def size(self) -> int:
        return int(self._index.ntotal)

    def embed(self, text: str) -> np.ndarray:
        vec = self._model.encode([text or ""], normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False)[0]
        return vec.astype(np.float32, copy=False)

    def search(self, vector: np.ndarray, k: int = 5, exclude_ids: set[str] | None = None) -> list[dict]:
        """Return precedent dicts exactly as in the HTTP response, sorted by similarity descending.
        exclude_ids drops those KB tickets (threshold tuning uses it to skip a val ticket's self-match)."""
        if k <= 0 or self.size == 0:
            return []
        exclude = exclude_ids or set()
        n = min(self.size, k + len(exclude) + 5)
        query = np.ascontiguousarray(np.asarray(vector, dtype=np.float32).reshape(1, -1))
        sims, idxs = self._index.search(query, n)

        out: list[dict] = []
        for sim, idx in zip(sims[0], idxs[0]):
            if idx < 0:
                continue
            row = self._rows[idx]
            if row["ticket_id"] in exclude:
                continue
            out.append({
                "ticket_id": row["ticket_id"],
                "similarity": round(float(min(max(sim, 0.0), 1.0)), 3),
                "language": row["language"],
                "subject": row["subject"],
                "body_snippet": row["body_snippet"],
                "answer_snippet": row["answer_snippet"],
                "answer": row["answer"],
                "type": row["type"],
                "queue": row["queue"],
                "priority": row["priority"],
                "tags": list(row["tags"]),
            })
            if len(out) == k:
                break
        return out


if __name__ == "__main__":
    import time

    r = Retriever.load()
    print(f"Loaded index: {r.size:,} vectors, model {r.model_name}")
    queries = {
        "en VPN": "VPN not connecting for remote staff since this morning, client times out",
        "de printer": "Drucker druckt nur leere Seiten nach dem Treiber-Update",
        "en billing": "I was charged twice for my subscription this month, please check the invoice",
    }
    r.search(r.embed("warm up"), k=5)
    for name, q in queries.items():
        t0 = time.perf_counter()
        v = r.embed(q)
        t1 = time.perf_counter()
        hits = r.search(v, k=5)
        t2 = time.perf_counter()
        print(f"\n== {name}: embed {1000 * (t1 - t0):.1f} ms, search {1000 * (t2 - t1):.1f} ms")
        for h in hits[:3]:
            print(f"  {h['ticket_id']}  sim={h['similarity']:.3f}  [{h['language']}] {h['queue']} / {h['priority']}"
                  f"  | {(h['subject'] or h['body_snippet'])[:70]!r}")
