"""B1.3: embed the KB split into FAISS (owner: Karanpatel3114).

Run from the repo root:  python -m agent.build_index

Reads ONLY data/kb_train.parquet (all rows, including is_val). From data/test_inputs.parquet it
reads ONLY the ticket_id column, to assert that no test ticket ends up in the index.

Writes:
    artifacts/kb.faiss          IndexFlatIP over L2-normalised embeddings (cosine)
    artifacts/kb_meta.parquet   one row per vector, in index order; text fields are PII-masked
    artifacts/kb_index_info.json  model name, dim, row count, split fingerprint, build time
    artifacts/kb_common_terms.json  terms in >= 2% of KB tickets (used by BurstDetector)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# IMPORT ORDER MATTERS (macOS segfault otherwise): torch before faiss, faiss single-threaded.
# See agent/retrieve.py.
from sentence_transformers import SentenceTransformer  # noqa: I001  (must precede faiss)
import faiss  # noqa: E402

from agent.burst import COMMON_TERMS_FILE, tokenize
from agent.pii import mask_pii
from shared.text import build_text

DEFAULT_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BODY_SNIPPET_CHARS = 300
MAX_SEQ_LENGTH = 256

META_COLUMNS = ["ticket_id", "language", "subject", "body_snippet", "answer",
                "type", "queue", "priority", "tags", "is_val"]


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip()


def _tags(row: pd.Series) -> list[str]:
    if "tags" in row.index and row["tags"] is not None and not isinstance(row["tags"], float):
        return [str(t) for t in list(row["tags"]) if _clean(t)]
    return [_clean(row[c]) for c in (f"tag_{i}" for i in range(1, 9)) if c in row.index and _clean(row[c])]


def _masked(text: str) -> str:
    return mask_pii(text)[0]


def write_common_terms(texts: list[str], out_dir: Path, min_df: float = 0.02) -> int:
    """Save terms that appear in >= min_df of KB tickets. BurstDetector treats every other term
    as "rare" and requires burst members to share one (see agent/burst.py)."""
    df: dict[str, int] = {}
    for t in texts:
        for w in set(tokenize(t)):
            df[w] = df.get(w, 0) + 1
    cutoff = min_df * len(texts)
    common = sorted(w for w, c in df.items() if c >= cutoff)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / COMMON_TERMS_FILE).write_text(json.dumps(common, ensure_ascii=False))
    return len(common)


def build(data_dir: Path, out_dir: Path, model_name: str) -> dict:
    faiss.omp_set_num_threads(1)
    t0 = time.perf_counter()
    kb = pd.read_parquet(data_dir / "kb_train.parquet")
    test_ids = pd.read_parquet(data_dir / "test_inputs.parquet", columns=["ticket_id"])["ticket_id"]

    # Leakage guard (docs/data-and-leakage.md §5 rule 3).
    assert kb["ticket_id"].is_unique, "duplicate ticket_id in kb_train"
    assert set(kb["ticket_id"]).isdisjoint(set(test_ids)), "LEAKAGE: a test ticket_id is in kb_train"
    fingerprint = hashlib.sha256(",".join(test_ids).encode()).hexdigest()[:12]
    print(f"KB rows: {len(kb):,} (val: {int(kb['is_val'].sum()):,})  split fingerprint: {fingerprint}")

    texts = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]

    model = SentenceTransformer(model_name, device=os.getenv("SENTINEL_EMBED_DEVICE") or None)
    model.max_seq_length = MAX_SEQ_LENGTH
    print(f"Embedding with {model_name} on {model.device} ...")
    t_emb = time.perf_counter()
    vecs = model.encode(texts, batch_size=64, normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=True).astype(np.float32)
    emb_s = time.perf_counter() - t_emb

    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)

    meta = pd.DataFrame({
        "ticket_id": kb["ticket_id"].astype(str),
        "language": kb["language"].map(_clean),
        "subject": [_masked(_clean(s)) for s in kb["subject"]],
        "body_snippet": [_masked(_clean(b))[:BODY_SNIPPET_CHARS] for b in kb["body"]],
        "answer": [_masked(_clean(a)) for a in kb["answer"]],
        "type": kb["type"].map(_clean),
        "queue": kb["queue"].map(_clean),
        "priority": kb["priority"].map(_clean),
        "tags": [_tags(row) for _, row in kb.iterrows()],
        "is_val": kb["is_val"].astype(bool),
    })[META_COLUMNS]
    assert len(meta) == index.ntotal

    out_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out_dir / "kb.faiss"))
    meta.to_parquet(out_dir / "kb_meta.parquet", index=False)
    n_common = write_common_terms(texts, out_dir)
    info = {
        "common_terms": n_common,
        "embed_model": model_name,
        "dim": int(vecs.shape[1]),
        "rows": int(index.ntotal),
        "val_rows": int(meta["is_val"].sum()),
        "split_fingerprint": fingerprint,
        "max_seq_length": MAX_SEQ_LENGTH,
        "embed_seconds": round(emb_s, 1),
        "build_seconds": round(time.perf_counter() - t0, 1),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / "kb_index_info.json").write_text(json.dumps(info, indent=2))
    return info


def main() -> None:
    load_dotenv()
    data_dir = Path(os.getenv("SENTINEL_DATA_DIR", "data"))
    out_dir = Path(os.getenv("SENTINEL_ARTIFACTS_DIR", "artifacts"))
    model_name = os.getenv("SENTINEL_EMBED_MODEL", DEFAULT_EMBED_MODEL)
    info = build(data_dir, out_dir, model_name)
    print(f"Indexed {info['rows']:,} tickets in {info['build_seconds']} s "
          f"(embedding {info['embed_seconds']} s) -> {out_dir / 'kb.faiss'}")


if __name__ == "__main__":
    main()
