"""B1: language detection for incoming tickets (owner: Karanpatel3114).

Contract (docs/contract.md §2):
    detect_language(text) -> {"code": str, "confidence": float, "reply_language": "en" | "de"}

The detector is built once at import time. Lingua loads its n-gram models lazily on the
first call, so the API warm-up request pays that cost, not the first judge ticket.
"""
from __future__ import annotations

import re

from lingua import Language, LanguageDetectorBuilder

_LANGUAGES = [
    Language.ENGLISH,
    Language.GERMAN,
    Language.FRENCH,
    Language.SPANISH,
    Language.PORTUGUESE,
    Language.ITALIAN,
]

_DETECTOR = LanguageDetectorBuilder.from_languages(*_LANGUAGES).build()

# Placeholder tokens should not vote on the language: our own PII masks ([EMAIL], [PHONE]...)
# and the dataset's own ones (<tel_num>, <name>, [Name], {name}...). On a short German
# ticket, "[PHONE]" would otherwise push the result towards English.
_PLACEHOLDER_RE = re.compile(r"\[[A-Za-z_ ]{2,30}\]|<[A-Za-z_ ]{2,30}>|\{[A-Za-z_ ]{2,30}\}")
_LETTER_RE = re.compile(r"[^\W\d_]")

_DEFAULT = {"code": "en", "confidence": 0.0, "reply_language": "en"}

# Tie-break for close en/de calls. German IT tickets are full of English product words
# ("Der Outlook Client crasht beim Login..."), which can tip lingua towards English. Function
# words are a much steadier signal of the sentence's actual language.
_TIE_MARGIN = 0.90  # only consider a tie-break when the top language is below this confidence
_DE_WORDS = {
    "der", "die", "das", "den", "dem", "des", "und", "ist", "nicht", "mit", "beim", "vom", "zum", "zur",
    "ein", "eine", "einen", "auf", "für", "bei", "seit", "wir", "sie", "ich", "uns", "unser", "unsere",
    "kann", "können", "wird", "werden", "wurde", "keine", "kein", "noch", "auch", "aber", "oder", "bitte",
    "nach", "über", "funktioniert", "geht", "mehr", "war", "hat", "haben", "sind", "dass", "wenn", "schon",
}
_EN_WORDS = {
    "the", "and", "is", "not", "with", "for", "on", "at", "we", "you", "our", "can", "cannot", "can't",
    "will", "would", "was", "were", "has", "have", "are", "this", "that", "since", "please", "after",
    "from", "it", "of", "to", "in", "a", "an", "be", "been", "but", "or", "any", "all", "when", "does",
}
_TOKEN_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")


def _function_word_vote(text: str) -> str | None:
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    de = sum(t in _DE_WORDS for t in tokens)
    en = sum(t in _EN_WORDS for t in tokens)
    if de > en:
        return "de"
    if en > de:
        return "en"
    return None


def detect_language(text: str) -> dict:
    """Return {"code": "en"|"de"|<other ISO 639-1>, "confidence": float, "reply_language": "en"|"de"}.

    reply_language is "de" only when code == "de", otherwise "en".
    Empty, numbers-only or undetectable text returns {"code": "en", "confidence": 0.0, "reply_language": "en"}.
    """
    if not text:
        return dict(_DEFAULT)
    cleaned = _PLACEHOLDER_RE.sub(" ", text)
    if not _LETTER_RE.search(cleaned):
        return dict(_DEFAULT)

    values = _DETECTOR.compute_language_confidence_values(cleaned)
    if not values or values[0].value <= 0.0:
        return dict(_DEFAULT)

    scores = {v.language.iso_code_639_1.name.lower(): float(v.value) for v in values}
    code = values[0].language.iso_code_639_1.name.lower()
    confidence = float(values[0].value)

    if code in ("en", "de") and confidence < _TIE_MARGIN:
        vote = _function_word_vote(cleaned)
        if vote is not None and vote != code:
            # Report the confidence of the language we switched to, plus what the vote moved over.
            code, confidence = vote, max(scores.get(vote, 0.0), 1.0 - confidence)

    return {
        "code": code,
        "confidence": round(confidence, 3),
        "reply_language": "de" if code == "de" else "en",
    }


if __name__ == "__main__":
    import time

    samples = [
        "My laptop cannot connect to the VPN since this morning.",
        "Seit heute Morgen kann sich niemand mehr mit dem VPN verbinden.",
        "VPN geht nicht",
        "Der Outlook Client crasht beim Login, das Update vom Patch Tuesday war schuld.",
        "",
        "12345 678",
        "Bonjour, mon imprimante ne fonctionne plus.",
    ]
    detect_language("warm up")
    for s in samples:
        t0 = time.perf_counter()
        r = detect_language(s)
        ms = (time.perf_counter() - t0) * 1000
        print(f"{ms:6.2f} ms  {r}  <- {s[:60]!r}")
