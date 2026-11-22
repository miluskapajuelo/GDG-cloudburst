"""B1.4 tests: agent.retrieve.Retriever against the built index.
Run: python -m pytest tests/test_b1_retrieve.py -q   (skipped until `python -m agent.build_index` has run)
"""
import os
from pathlib import Path

import numpy as np
import pytest

ART = Path(os.getenv("SENTINEL_ARTIFACTS_DIR", "artifacts"))
pytestmark = pytest.mark.skipif(not (ART / "kb.faiss").exists(), reason="index not built yet")

CONTRACT_KEYS = ["ticket_id", "similarity", "language", "subject", "body_snippet", "answer_snippet",
                 "answer", "type", "queue", "priority", "tags"]


@pytest.fixture(scope="module")
def retriever():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from agent.retrieve import Retriever
    return Retriever.load()


def test_embed_shape_and_norm(retriever):
    v = retriever.embed("VPN geht nicht")
    assert v.shape == (384,) and v.dtype == np.float32
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-4


def test_search_contract_shape(retriever):
    hits = retriever.search(retriever.embed("I was charged twice for my subscription"), k=5)
    assert 1 <= len(hits) <= 5
    for h in hits:
        assert list(h) == CONTRACT_KEYS
        assert h["ticket_id"].startswith("TKT-") and 0.0 <= h["similarity"] <= 1.0
        assert len(h["answer_snippet"]) <= 400 and h["answer"].startswith(h["answer_snippet"])
        assert isinstance(h["tags"], list) and isinstance(h["similarity"], float)
    sims = [h["similarity"] for h in hits]
    assert sims == sorted(sims, reverse=True)


def test_exclude_ids(retriever):
    v = retriever.embed("VPN connection keeps dropping")
    top = retriever.search(v, k=5)
    excluded = {top[0]["ticket_id"], top[1]["ticket_id"]}
    again = retriever.search(v, k=5, exclude_ids=excluded)
    assert len(again) == 5 and not excluded & {h["ticket_id"] for h in again}


def test_search_from_worker_threads(retriever):
    """The API serves requests on worker threads. faiss's thread setting is per-thread, and on
    macOS a multi-threaded faiss search next to torch's OpenMP segfaults (exit 139)."""
    from concurrent.futures import ThreadPoolExecutor

    queries = ["VPN geht nicht", "charged twice for my subscription", "Drucker druckt nicht",
               "Outlook crashes on startup", "Server antwortet nicht", "password reset email missing"]

    def one(q):
        return retriever.search(retriever.embed(q), k=5)[0]["ticket_id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, queries * 3))
    assert len(results) == 18 and all(r.startswith("TKT-") for r in results)


def test_index_has_no_test_ids(retriever):
    import pandas as pd
    data = Path(os.getenv("SENTINEL_DATA_DIR", "data"))
    test_path = data / "test_inputs.parquet"
    if not test_path.exists():
        pytest.skip("split not present")
    test_ids = set(pd.read_parquet(test_path, columns=["ticket_id"])["ticket_id"])
    assert not test_ids & {r["ticket_id"] for r in retriever._rows}
