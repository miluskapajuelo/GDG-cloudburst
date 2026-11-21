"""B1.6 tests: agent.burst.BurstDetector. Run: python -m pytest tests/test_b1_burst.py -q

The synthetic tests need no model. The demo test uses the real embedding model only if it is
already cached locally (it is skipped otherwise, so the suite never needs the network).
"""
import os

import numpy as np
import pytest

from agent.burst import BurstDetector

GENERIC = {"system", "issue", "problem", "support", "help", "please", "dear", "team"}


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def _near(base, noise, rng):
    return _unit(base + noise * rng.standard_normal(base.shape))


def test_cluster_of_three_activates_and_unrelated_stays_inactive():
    rng = np.random.default_rng(0)
    base = rng.standard_normal(384)
    d = BurstDetector(0.65, 3, 15, common_terms=GENERIC)
    r1 = d.observe("r1", _near(base, 0.02, rng), "VPN down for the office", ts=1000)
    r2 = d.observe("r2", _near(base, 0.02, rng), "VPN-Verbindung bricht ab", ts=1060)
    r3 = d.observe("r3", _near(base, 0.02, rng), "VPN handshake timeout", ts=1120)
    assert not r1["active"] and not r2["active"]
    assert r3["active"] and r3["cluster_size"] == 3
    assert r3["request_ids"] == ["r1", "r2", "r3"]
    assert "VPN" in r3["label"]
    other = d.observe("r4", _unit(rng.standard_normal(384)), "Recipe for chocolate cake", ts=1180)
    assert other == {"active": False, "cluster_size": 1, "window_minutes": 15, "label": None, "request_ids": []}


def test_similar_vectors_without_shared_rare_term_do_not_cluster():
    rng = np.random.default_rng(1)
    base = rng.standard_normal(384)
    d = BurstDetector(0.65, 3, 15, common_terms=GENERIC)
    for i, s in enumerate(["Dear support team, system issue", "Problem with system, please help", "Issue: system"]):
        r = d.observe(f"r{i}", _near(base, 0.02, rng), s, ts=1000 + i)
    assert not r["active"]


def test_window_expiry_and_reset():
    rng = np.random.default_rng(2)
    base = rng.standard_normal(384)
    d = BurstDetector(0.65, 3, 15, common_terms=GENERIC)
    d.observe("old1", _near(base, 0.02, rng), "printer jam", ts=0)
    d.observe("old2", _near(base, 0.02, rng), "printer jam", ts=10)
    late = d.observe("new", _near(base, 0.02, rng), "printer jam", ts=16 * 60)  # both old ones expired
    assert not late["active"]
    d.observe("a", _near(base, 0.02, rng), "printer jam", ts=17 * 60)
    assert d.observe("b", _near(base, 0.02, rng), "printer jam", ts=17 * 60 + 5)["active"]
    d.reset()
    assert not d.observe("c", _near(base, 0.02, rng), "printer jam", ts=17 * 60 + 10)["active"]


def _cached_model():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
    except Exception:
        return None


def test_demo_vpn_burst_mixed_en_de():
    """demo-10..13 must activate by demo-12; an unrelated ticket must not join."""
    model = _cached_model()
    if model is None:
        pytest.skip("embedding model not cached locally")
    tickets = [
        "VPN down for whole office\n\nNone of our staff can connect to the corporate VPN since about 9:00. The client times out during the handshake.",
        "VPN-Verbindung bricht ab\n\nSeit ca. 9 Uhr kommt keine VPN-Verbindung mehr zustande, der Client bricht beim Verbindungsaufbau mit Timeout ab. Das ganze Team ist betroffen.",
        "VPN handshake timeout for all remote employees, started this morning around 9.",
        "Remote access not working\n\nOur remote workers can't reach internal systems, the VPN connection keeps timing out. Started today at 9am.",
        "Quick question\n\nCan you recommend a good recipe for a vegan chocolate cake and tell me tomorrow's weather in Berlin?",
    ]
    vecs = model.encode(tickets, normalize_embeddings=True)
    d = BurstDetector(0.65, 3, 15, common_terms=GENERIC)
    out = [d.observe(f"demo-{10 + i}", v, t[:120], ts=1000 + 30 * i) for i, (t, v) in enumerate(zip(tickets, vecs))]
    assert [o["active"] for o in out] == [False, False, True, True, False]
    assert out[3]["cluster_size"] == 4
