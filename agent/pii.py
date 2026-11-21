"""B1: PII masking before any external LLM call (owner: Karanpatel3114).

Contract (docs/contract.md §2):
    mask_pii(text) -> (masked_text, counts)   counts always has the 6 keys below.

Patterns run in a fixed order so that longer, more specific patterns win:
IBAN -> EMAIL -> CARD -> IP -> PHONE -> ACCOUNT. A replaced span becomes a bracketed
placeholder with no digits, so later patterns can't match inside it.

The dataset already contains its own placeholders (<tel_num>, <name>, <acc_num>, [Name], ...).
They contain no digits and are left unchanged.
"""
from __future__ import annotations

import re
from typing import Callable

PII_KEYS: tuple[str, ...] = ("EMAIL", "PHONE", "IP", "IBAN", "CARD", "ACCOUNT")

_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")

# 13-19 digits, optionally grouped by spaces or dashes. Luhn-checked to avoid eating phone numbers.
_CARD_RE = re.compile(r"(?<![\w-])(?:\d[ -]?){12,18}\d(?![\w-])")

_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
# A sentence-ending period is fine ("from 192.168.14.22."); a period followed by a digit is not.
_IPV4_RE = re.compile(rf"(?<!\d)(?<!\d\.){_OCTET}(?:\.{_OCTET}){{3}}(?!\d|\.\d)")
# Simple IPv6: the full 8-group form, or a compressed form with "::" between hex groups.
_IPV6_RE = re.compile(
    r"(?<![\w:])(?:"
    r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,6}:(?:[0-9A-Fa-f]{1,4}:){0,5}[0-9A-Fa-f]{1,4}"
    r")(?![\w:])"
)

# International: +49 ... / 0049 ... (also +1234567890 as seen in the KB).
_PHONE_INTL_RE = re.compile(r"(?<![\w+])(?:\+|00)[1-9]\d{0,2}[ \-/]?(?:\(0\)[ \-/]?)?(?:\d[ \-/]?){5,12}\d(?![\w])")
# National: a leading 0 and at least 7 digits in total. Dots are not allowed as separators,
# so dates such as 21.11.2026 never match. The lookbehind blocks "-" so TKT-01234 is safe.
_PHONE_NATL_RE = re.compile(r"(?<![\w.\-/])0\d{2,5}(?:[ \-/]?\d){4,10}(?![\w.]|-\d)")
# North American: (555) 123-4567 and 555-123-4567.
_PHONE_NA_RE = re.compile(r"(?<![\w-])(?:\(\d{3}\) ?|\d{3}-)\d{3}-\d{4}(?![\w-])")

# Keyword followed by a number of 5+ digits. Only the number is replaced; the keyword stays.
_ACCOUNT_RE = re.compile(
    r"(?P<kw>\b(?:account|acct|customer|kunden|konto|vertrags)"
    r"(?:[ \-]?(?:no|nr|number|nummer|num|id|#))?\.?"
    r"|\bkundennummer|\bkontonummer|\bvertragsnummer)"
    r"(?P<sep>\s*(?:no\.?|nr\.?|number|#)?\s*[:#]?\s*)"
    r"(?P<num>\d(?:[ \-]?\d){4,})(?!\d)",
    re.IGNORECASE,
)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _sub(pattern: re.Pattern, text: str, key: str, counts: dict[str, int],
         accept: Callable[[re.Match], bool] | None = None) -> str:
    def repl(m: re.Match) -> str:
        if accept is not None and not accept(m):
            return m.group(0)
        counts[key] += 1
        return f"[{key}]"

    return pattern.sub(repl, text)


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace PII with [EMAIL] [PHONE] [IP] [IBAN] [CARD] [ACCOUNT].
    Return (masked_text, counts). The counts dict always has all 6 keys."""
    counts = {k: 0 for k in PII_KEYS}
    if not text:
        return text or "", counts

    out = _sub(_IBAN_RE, text, "IBAN", counts)
    out = _sub(_EMAIL_RE, out, "EMAIL", counts)
    out = _sub(_CARD_RE, out, "CARD", counts,
               accept=lambda m: _luhn_ok(re.sub(r"\D", "", m.group(0))))
    out = _sub(_IPV4_RE, out, "IP", counts)
    out = _sub(_IPV6_RE, out, "IP", counts)
    out = _sub(_PHONE_INTL_RE, out, "PHONE", counts)
    out = _sub(_PHONE_NATL_RE, out, "PHONE", counts)
    out = _sub(_PHONE_NA_RE, out, "PHONE", counts)

    def acct_repl(m: re.Match) -> str:
        counts["ACCOUNT"] += 1
        return f"{m.group('kw')}{m.group('sep')}[ACCOUNT]"

    out = _ACCOUNT_RE.sub(acct_repl, out)
    return out, counts


if __name__ == "__main__":
    demo = ("Hello, my account is locked after too many login attempts. My email is jane.doe@example.com, "
            "phone +49 170 1234567, customer no 88412093. The attempts came from IP 192.168.14.22. "
            "Ticket TKT-01234 from 21.11.2026. IBAN DE89 3704 0044 0532 0130 00, card 4111 1111 1111 1111.")
    masked, c = mask_pii(demo)
    print(masked)
    print(c)
