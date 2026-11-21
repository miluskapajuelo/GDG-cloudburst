"""B1.2 tests: agent.pii.mask_pii. Run: python -m pytest tests/test_b1_pii.py -q"""
import pytest

from agent.pii import PII_KEYS, mask_pii


def test_counts_always_have_all_keys():
    masked, counts = mask_pii("")
    assert masked == ""
    assert set(counts) == set(PII_KEYS) and all(v == 0 for v in counts.values())


def test_demo_09_ticket():
    body = ("Hello, my account is locked after too many login attempts. My email is jane.doe@example.com, "
            "phone +49 170 1234567, customer no 88412093. The attempts came from IP 192.168.14.22. Please unlock it.")
    masked, counts = mask_pii(body)
    assert counts == {"EMAIL": 1, "PHONE": 1, "IP": 1, "IBAN": 0, "CARD": 0, "ACCOUNT": 1}
    for raw in ("jane.doe@example.com", "+49 170 1234567", "88412093", "192.168.14.22"):
        assert raw not in masked
    assert "customer no [ACCOUNT]" in masked


@pytest.mark.parametrize(
    "text, key",
    [
        ("Contact me at max.mustermann@firma.de please", "EMAIL"),
        ("Bitte überweisen Sie auf DE89 3704 0044 0532 0130 00 danke", "IBAN"),
        ("Bitte überweisen Sie auf DE89370400440532013000 danke", "IBAN"),
        ("My card 4111 1111 1111 1111 was charged twice", "CARD"),
        ("Card number 4111-1111-1111-1111", "CARD"),
        ("Rufen Sie mich an: 030 12345678", "PHONE"),
        ("Mobil: 0170/1234567", "PHONE"),
        ("Tel. 0049 30 1234567", "PHONE"),
        ("Call +1234567890 any time", "PHONE"),
        ("Call me at (555) 123-4567", "PHONE"),
        ("Meine Kundennummer: 4471209 bitte prüfen", "ACCOUNT"),
        ("Kontonummer 1234567890", "ACCOUNT"),
        ("acct #998877 is suspended", "ACCOUNT"),
        ("Server at 2001:0db8:85a3:0000:0000:8a2e:0370:7334 is down", "IP"),
        ("Gateway fe80::1ff:fe23:4567:890a unreachable", "IP"),
    ],
)
def test_each_type(text, key):
    masked, counts = mask_pii(text)
    assert counts[key] == 1, (masked, counts)
    assert f"[{key}]" in masked
    assert sum(counts.values()) == 1, (masked, counts)


def test_ipv4_in_log_line():
    log = "2026-11-21 08:14:02 ERROR vpn-gw: auth failed for client 10.20.30.40 port 4500"
    masked, counts = mask_pii(log)
    assert counts["IP"] == 1
    assert "10.20.30.40" not in masked
    assert "2026-11-21 08:14:02" in masked  # timestamp untouched
    assert counts["PHONE"] == 0


@pytest.mark.parametrize(
    "text",
    [
        "See ticket TKT-01234 for details",
        "Termin am 21.11.2026 um 08:00 Uhr",
        "Version 2.4.1 released on 2026-11-21",
        "Error code 0x80070005 after update",
        "Fehler 809 bei der Authentifizierung",
        "Please call <tel_num> or ask for <name>, acc <acc_num>, [Name], [Telefonnummer]",
        "About 300 employees are affected since 07:40",
        "Our order 1234 of 25 licenses",
    ],
)
def test_no_false_positives(text):
    masked, counts = mask_pii(text)
    assert masked == text, (masked, counts)
    assert sum(counts.values()) == 0


def test_luhn_rejects_random_long_number():
    masked, counts = mask_pii("Reference 1234 5678 9012 3456 for your records")
    assert counts["CARD"] == 0


def test_idempotent():
    once, _ = mask_pii("Mail jane@example.com, IP 192.168.1.1, Tel +49 170 1234567")
    twice, counts = mask_pii(once)
    assert twice == once and sum(counts.values()) == 0
