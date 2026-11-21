"""Environment configuration and reference patterns for the escalation gate."""

import math
import os
import re
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _probability(name: str, default: float) -> float:
    variable = f"SENTINEL_{name}"
    value = float(os.getenv(variable, str(default)))
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{variable} must be between 0 and 1.")
    return value


def _positive_int(name: str, default: int) -> int:
    variable = f"SENTINEL_{name}"
    value = int(os.getenv(variable, str(default)))
    if value < 1:
        raise ValueError(f"{variable} must be a positive integer.")
    return value


T_HIGH_PRIORITY_P = _probability("T_HIGH_PRIORITY_P", 0.20)
T_INCIDENT_P = _probability("T_INCIDENT_P", 0.30)
T_CONF_TYPE = _probability("T_CONF_TYPE", 0.50)
T_CONF_PRIORITY = _probability("T_CONF_PRIORITY", 0.50)
T_CONF_QUEUE = _probability("T_CONF_QUEUE", 0.25)
T_SIM = _probability("T_SIM", 0.50)
TOP_K = _positive_int("TOP_K", 5)
BURST_SIM = _probability("BURST_SIM", 0.65)
BURST_MIN = _positive_int("BURST_MIN", 3)
BURST_WINDOW_MIN = _positive_int("BURST_WINDOW_MIN", 15)

# Word target for a grounded (status OK) reply, not counting [TKT-...] citations.
REPLY_MIN_WORDS = _positive_int("REPLY_MIN_WORDS", 80)
REPLY_MAX_WORDS = _positive_int("REPLY_MAX_WORDS", 100)
if REPLY_MIN_WORDS > REPLY_MAX_WORDS:
    raise ValueError("SENTINEL_REPLY_MIN_WORDS must not exceed SENTINEL_REPLY_MAX_WORDS.")

LLM_MODEL = os.getenv("SENTINEL_LLM_MODEL", "gemini-3.5-flash-lite").strip()
LLM_TIMEOUT_S = float(os.getenv("SENTINEL_LLM_TIMEOUT_S", "30"))
if not math.isfinite(LLM_TIMEOUT_S) or LLM_TIMEOUT_S <= 0:
    raise ValueError("SENTINEL_LLM_TIMEOUT_S must be a positive number of seconds.")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()


SENSITIVE_LEXICON: dict[str, list[str]] = {
    "REFUND_COMPENSATION": [
        "refund", "reimburse", "compensation", "money back", "chargeback", "credit note",
        "rückerstattung", "erstatten", "entschädigung", "geld zurück", "gutschrift",
    ],
    "PRICING_DISCOUNT": [
        "price", "pricing", "quote", "discount", "license fee", "cost per",
        "preis", "rabatt", "lizenzgebühr", "kostenvoranschlag",
    ],
    "LEGAL_CONTRACT": [
        "lawsuit", "legal action", "liability", "lawyer", "terminate contract", "gdpr",
        "delete all my data", "klage", "rechtliche schritte", "haftung", "anwalt",
        "vertrag kündigen", "dsgvo", "datenlöschung",
    ],
    "SLA_GUARANTEE": [
        "sla", "guarantee", "uptime commitment", "service credit", "penalty",
        "garantie", "verfügbarkeitszusage", "vertragsstrafe",
    ],
    "SECURITY_OVERRIDE": [
        "disable mfa", "bypass", "share password", "give me admin", "root access",
        "mfa deaktivieren", "passwort mitteilen", "adminrechte geben", "umgehen",
    ],
}

INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bignore\s+(?:(?:all|any|the)\s+)?"
        r"(?:previous|prior|above|earlier)\s+(?:instructions|rules|prompts?)\b",
        r"\bdisregard\s+(?:(?:all|any|the)\s+)?"
        r"(?:previous|prior|above)\s+(?:instructions|rules)\b",
        r"\b(?:reveal|print|show)\s+(?:your|the)\s+(?:system\s+)?prompt\b",
        r"\b(?:you\s+are\s+now|act\s+as\s+(?:an?\s+)?(?:admin|system|developer)"
        r"|developer\s+mode|jailbreak)\b",
        r"</?(?:system|ticket|precedents?|instructions?)(?:\s[^<>]*)?\s*/?>",
        r"\bignorier(?:e|en)?\s+(?:sie\s+)?(?:bitte\s+)?(?:(?:alle|die)\s+)?"
        r"(?:vorherigen|obigen|bisherigen)\s+(?:anweisungen|regeln)\b",
        r"\bvergiss\s+(?:(?:alle|deine)\s+)?(?:anweisungen|regeln)\b",
    )
)
