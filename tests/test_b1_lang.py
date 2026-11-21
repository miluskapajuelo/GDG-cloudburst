"""B1.1 tests: agent.lang.detect_language. Run: python -m pytest tests/test_b1_lang.py -q"""
import time

import pytest

from agent.lang import detect_language


@pytest.mark.parametrize(
    "text, code",
    [
        ("My laptop cannot connect to the VPN since this morning. Can you help?", "en"),
        ("Seit heute Morgen kann sich niemand mehr mit dem VPN verbinden.", "de"),
        ("VPN geht nicht", "de"),
        ("Der Outlook Client crasht beim Login, seit dem Update vom Dienstag funktioniert nichts mehr.", "de"),
        ("Der Outlook Client crasht beim Login, das Update vom Patch Tuesday war schuld.", "de"),
        ("SAP Fiori Launchpad zeigt nach dem Single Sign-On Update nur einen Blank Screen", "de"),
        ("The Drucker in Building 2 is not printing, error on the Netzwerk page", "en"),
    ],
)
def test_detects_en_de(text, code):
    r = detect_language(text)
    assert r["code"] == code
    assert r["reply_language"] == code
    assert 0.0 < r["confidence"] <= 1.0


@pytest.mark.parametrize("text", ["", "   ", "12345 678", "[EMAIL] [PHONE]"])
def test_empty_or_undetectable_defaults_to_en(text):
    assert detect_language(text) == {"code": "en", "confidence": 0.0, "reply_language": "en"}


def test_other_language_replies_in_english():
    r = detect_language("Bonjour, mon imprimante ne fonctionne plus depuis la mise à jour.")
    assert r["code"] == "fr"
    assert r["reply_language"] == "en"


def test_placeholders_do_not_flip_short_german():
    r = detect_language("Bitte rufen Sie mich zurück: [PHONE], <tel_num>")
    assert r["code"] == "de"


def test_fast_after_warmup():
    detect_language("warm up the detector")
    t0 = time.perf_counter()
    for _ in range(20):
        detect_language("Seit heute Morgen kann sich niemand mehr mit dem VPN verbinden.")
    assert (time.perf_counter() - t0) / 20 < 0.005
