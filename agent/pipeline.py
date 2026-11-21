"""Combine retrieval, escalation and grounded drafting for a triage request."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from . import config
from .citations import validate_citations
from .draft import DraftError, generate_draft
from .gate import finalize_escalation, pre_draft_gate
from .prompts import MAX_RESOLUTION_CHARS

if TYPE_CHECKING:
    from .burst import BurstDetector
    from .retrieve import Retriever


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1_000)


class AgentPipeline:
    def __init__(self, retriever: Retriever, burst: BurstDetector) -> None:
        self.retriever = retriever
        self.burst = burst

    def run(
        self,
        request_id: str,
        text: str,
        language: dict,
        predictions: dict,
        *,
        skip_llm: bool = False,
    ) -> dict:
        """Triage a PII-masked ticket using the supplied predictions and KB index."""
        started = perf_counter()
        vector = self.retriever.embed(text)
        precedents = self.retriever.search(vector, k=config.TOP_K)
        latency_ms = {"retrieve": _elapsed_ms(started), "gate": 0, "generate": 0}
        burst = self.burst.observe(request_id, vector, summary=text[:120])

        started = perf_counter()
        pre = pre_draft_gate(predictions, precedents, text)
        should_draft = not skip_llm and pre["allow_draft"]
        latency_ms["gate"] = _elapsed_ms(started)

        draft, llm_error = None, None
        if should_draft:
            started = perf_counter()
            try:
                draft = generate_draft(
                    text, language["reply_language"], precedents,
                    for_human_review=bool(pre["reasons"]),
                )
            except DraftError as error:
                llm_error = str(error) or "Draft generation failed."
            except Exception:
                llm_error = "Unexpected draft generation error"
            latency_ms["generate"] = _elapsed_ms(started)

        started = perf_counter()
        problems = []
        if draft is not None:
            problems = validate_citations(
                draft["text"], draft["cited_ids"], {item["ticket_id"] for item in precedents},
                status=draft["status"],
                precedent_answers=(item["answer"][:MAX_RESOLUTION_CHARS] for item in precedents),
            )
        escalation = finalize_escalation(pre, draft, problems, llm_error)
        if draft is not None:
            draft["for_human_review"] = escalation["status"] == "ESCALATE"
        latency_ms["gate"] += _elapsed_ms(started)

        return {
            "precedents": precedents,
            "escalation": escalation,
            "draft": draft,
            "burst": burst,
            "latency_ms": latency_ms,
        }
