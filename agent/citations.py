"""Validate ticket references and figures in a resolution draft."""

import re
from collections.abc import Iterable
from decimal import Decimal

_CITATION = re.compile(r"\[(TKT-\d{5})\]")
_NUMBER = r"[+-]?\d+(?:[.,]\d+)*"
_CURRENCY = r"€|\$|euros?\b|eur\b|usd\b"
_FIGURE = re.compile(
    rf"(?<![\w.,])(?:(?P<prefix>{_CURRENCY})\s*(?P<prefix_amount>{_NUMBER})"
    rf"|(?P<amount>{_NUMBER})\s*(?P<suffix>{_CURRENCY}|%|prozent\b|percent\b))"
    r"(?!\d|[.,]\d)",
    re.IGNORECASE,
)
_UNITS = {
    "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "$": "USD", "usd": "USD", "%": "%", "prozent": "%", "percent": "%",
}


def extract_citation_ids(text: str) -> list[str]:
    """Return the distinct bracketed ticket IDs in order of first appearance."""
    return list(dict.fromkeys(_CITATION.findall(text)))


def _figure_keys(text: str) -> dict[tuple[Decimal | str, str], str]:
    figures = {}
    for match in _FIGURE.finditer(text):
        amount = match["prefix_amount"] or match["amount"]
        unit = _UNITS[(match["prefix"] or match["suffix"]).casefold()]
        decimal = amount.replace(",", ".")
        _, _, fraction = decimal.partition(".")
        # Preserve ambiguous thousands/decimal separators verbatim.
        key_amount = amount if "." in fraction or len(fraction) == 3 else Decimal(decimal)
        figures.setdefault((key_amount, unit), match[0])
    return figures


def validate_citations(
    draft_text: str,
    cited_ids: list[str],
    allowed_ids: set[str],
    *,
    status: str = "OK",
    precedent_answers: Iterable[str] | None = None,
) -> list[str]:
    """Check citations and, when answers are supplied, money and percentages."""
    problems = []
    text_ids = set(extract_citation_ids(draft_text))
    declared_ids = set(cited_ids)
    unknown_ids = (text_ids | declared_ids) - allowed_ids
    if unknown_ids:
        problems.append(f"Unknown ticket IDs: {', '.join(sorted(unknown_ids))}.")
    if status == "OK" and not text_ids:
        problems.append("Draft has no bracketed ticket citation.")
    if status == "INSUFFICIENT_EVIDENCE" and (text_ids or declared_ids):
        problems.append("A holding reply must have no ticket citations.")
    if text_ids != declared_ids:
        problems.append("Reported ticket IDs differ from the draft citations.")

    if precedent_answers is not None:
        supported = {key for answer in precedent_answers for key in _figure_keys(answer)}
        for key, figure in _figure_keys(draft_text).items():
            if key not in supported:
                problems.append(f"Figure is unsupported by precedent answers: {figure}.")
    return problems
