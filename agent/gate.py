"""Apply the escalation policy before and after draft generation."""

import re
from functools import cache

from . import config


_WHOLE_WORD_ENDINGS = {"sla": r"s?\b", "umgehen": r"\b"}


@cache
def _sensitive_term_pattern(term: str) -> re.Pattern[str]:
    folded_term = term.casefold()
    ending = _WHOLE_WORD_ENDINGS.get(folded_term, "")
    return re.compile(rf"\b{re.escape(folded_term)}{ending}")


def pre_draft_gate(predictions: dict, precedents: list[dict], text: str) -> dict:
    """Collect all pre-draft reasons and whether the pipeline may draft a reply."""
    reasons: list[dict[str, str]] = []
    high_priority = predictions["priority"]["probs"].get("high", 0.0)
    incident = predictions["type"]["probs"].get("Incident", 0.0)
    if high_priority >= config.T_HIGH_PRIORITY_P and incident >= config.T_INCIDENT_P:
        reasons.append({
            "code": "HIGH_PRIORITY_INCIDENT",
            "message": (
                f"Predicted high priority (p={high_priority:.2f}) and Incident (p={incident:.2f})."
            ),
        })

    injection_suspected = any(pattern.search(text) for pattern in config.INJECTION_PATTERNS)
    if injection_suspected:
        reasons.append({
            "code": "PROMPT_INJECTION_SUSPECTED",
            "message": "The ticket contains text that appears to override the drafting instructions.",
        })

    below_threshold = []
    for task, minimum in (
        ("type", config.T_CONF_TYPE),
        ("priority", config.T_CONF_PRIORITY),
        ("queue", config.T_CONF_QUEUE),
    ):
        confidence = predictions[task]["confidence"]
        if confidence < minimum:
            below_threshold.append(f"{task} ({confidence:.2f} < {minimum:.2f})")
    if below_threshold:
        reasons.append({
            "code": "LOW_CLASSIFIER_CONFIDENCE",
            "message": f"Classifier confidence below threshold for {', '.join(below_threshold)}.",
        })

    top_similarity = precedents[0]["similarity"] if precedents else None
    no_precedent = top_similarity is None or top_similarity < config.T_SIM
    if no_precedent:
        message = (
            f"No historical precedents were retrieved (minimum similarity {config.T_SIM:.2f})."
            if top_similarity is None
            else f"Best precedent similarity ({top_similarity:.2f}) is below {config.T_SIM:.2f}."
        )
        reasons.append({"code": "NO_PRECEDENT", "message": message})

    reasons.extend(_unsupported_requests(text, precedents))
    return {"reasons": reasons, "allow_draft": not (injection_suspected or no_precedent)}


def _unsupported_requests(text: str, precedents: list[dict]) -> list[dict[str, str]]:
    folded_text = text.casefold()
    answers = [precedent.get("answer", "").casefold() for precedent in precedents]
    unsupported = []
    for category, terms in config.SENSITIVE_LEXICON.items():
        patterns = [(term, _sensitive_term_pattern(term)) for term in terms]
        request_term = next((term for term, pattern in patterns if pattern.search(folded_text)), None)
        if request_term is None:
            continue
        has_support = any(pattern.search(answer) for _, pattern in patterns for answer in answers)
        if not has_support:
            unsupported.append(f'{category} ("{request_term}")')

    if not unsupported:
        return []
    return [{
        "code": "UNSUPPORTED_REQUEST",
        "message": f"Ticket requests {', '.join(unsupported)}; no retrieved precedent resolves this.",
    }]


def finalize_escalation(
    pre: dict, draft: dict | None, citation_problems: list[str], llm_error: str | None
) -> dict:
    """Add post-draft reasons and assign the final status, route, and badge."""
    reasons = list(pre["reasons"])
    if draft and draft["status"] == "INSUFFICIENT_EVIDENCE":
        reasons.append({
            "code": "LLM_INSUFFICIENT_EVIDENCE",
            "message": "There is insufficient historical evidence to draft a grounded resolution.",
        })
    if citation_problems:
        reasons.append({
            "code": "CITATION_CHECK_FAILED",
            "message": f"Draft validation found the following problems: {', '.join(citation_problems)}",
        })
    if llm_error is not None:
        message = "Draft generation is unavailable"
        if llm_error:
            message += f" ({llm_error})"
        reasons.append({
            "code": "LLM_UNAVAILABLE",
            "message": f"{message}.",
        })

    if any(reason["code"] == "HIGH_PRIORITY_INCIDENT" for reason in reasons):
        route = "ON_CALL"
        badge = "Escalate to On-Call Engineer"
    elif reasons:
        route = "HUMAN_REVIEW"
        badge = "Human Review Required"
    else:
        route = None
        badge = "Auto-Draft Ready"
    return {
        "status": "ESCALATE" if reasons else "AUTO_DRAFT",
        "route": route,
        "badge": badge,
        "reasons": reasons,
    }
