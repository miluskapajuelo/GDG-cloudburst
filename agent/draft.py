"""Generate structured, precedent-grounded replies with Gemini."""

import re
import time
from functools import cache
from html import unescape
from importlib import import_module
from typing import Literal

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from agent import config
from agent.citations import extract_citation_ids
from agent.prompts import MAX_RESOLUTION_CHARS, SYSTEM_PROMPT, build_user_message


class DraftOut(BaseModel):
    status: Literal["OK", "INSUFFICIENT_EVIDENCE"]
    reply: str
    cited_ids: list[str]


class DraftError(RuntimeError):
    """A safe, user-facing failure to generate a draft."""


def _transport_errors() -> tuple[tuple[type[Exception], ...], tuple[type[Exception], ...]]:
    timeouts: list[type[Exception]] = [TimeoutError]
    errors: list[type[Exception]] = [ConnectionError]
    # Older Gemini SDKs use httpx. Newer ones use httpx2 by default.
    for name in ("httpx", "httpx2"):
        try:
            transport = import_module(name)
        except ModuleNotFoundError:
            continue
        timeouts.append(transport.TimeoutException)
        errors.append(transport.RequestError)
    return tuple(timeouts), tuple(errors)


_TIMEOUT_ERRORS, _CONNECTION_ERRORS = _transport_errors()

_TICKET_ID = r"TKT-\d{5}"
_CITATION_TOKEN = re.compile(rf"\[{_TICKET_ID}\]")
_GROUPED_CITATION = re.compile(
    rf"\[\s*{_TICKET_ID}(?:(?:[\s,;/&]+|\s+(?i:and|und)\s+){_TICKET_ID})+\s*\]"
)
_WORD = re.compile(r"\w+(?:[-'’]\w+)*")


def _word_count(text: str) -> int:
    """Count the words in a reply, ignoring bracketed ticket citations."""
    return len(_WORD.findall(_CITATION_TOKEN.sub(" ", text)))


@cache
def _get_client() -> genai.Client:
    if not config.GEMINI_API_KEY:
        raise DraftError("Gemini API key is missing.")

    return genai.Client(
        vertexai=False,
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=max(1, int(config.LLM_TIMEOUT_S * 1000)),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def _call(system: str, contents: str) -> types.GenerateContentResponse:
    client = _get_client()
    generation_config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.2,
        max_output_tokens=2048,
        response_mime_type="application/json",
        response_schema=DraftOut,
    )

    # Back off on rate limits (429) and transient server errors: 2s, 4s, 8s.
    delays = [2.0, 4.0, 8.0]
    while True:
        try:
            return client.models.generate_content(
                model=config.LLM_MODEL, contents=contents, config=generation_config
            )
        except errors.APIError as error:
            if delays and error.code in (429, 500, 502, 503):
                time.sleep(delays.pop(0))
                continue
            raise DraftError(f"Gemini returned HTTP {error.code}.") from None
        except _TIMEOUT_ERRORS:
            raise DraftError("Gemini request timed out.") from None
        except _CONNECTION_ERRORS:
            raise DraftError("Could not reach Gemini.") from None


def _parse_response(response: types.GenerateContentResponse) -> DraftOut:
    feedback = response.prompt_feedback
    if feedback and feedback.block_reason not in (None, "BLOCKED_REASON_UNSPECIFIED"):
        raise DraftError("Gemini blocked the prompt.")
    if not response.candidates or response.candidates[0].finish_reason != "STOP":
        raise DraftError("Gemini did not finish the draft.")

    raw_text = response.text
    if not raw_text or not raw_text.strip():
        raise DraftError("Gemini returned an empty response.")

    if response.parsed is None:
        return DraftOut.model_validate_json(raw_text)
    return DraftOut.model_validate(response.parsed)


def generate_draft(
    text: str, reply_language: str, precedents: list[dict], for_human_review: bool
) -> dict:
    """Return a draft for the agent pipeline, raising DraftError on API failure."""
    user_message = build_user_message(text, reply_language, precedents)
    try:
        result = _parse_response(_call(SYSTEM_PROMPT, user_message))
    except ValidationError:
        raise DraftError("Gemini returned an invalid structured draft.") from None

    reply = unescape(result.reply).strip()
    if not reply:
        raise DraftError("Gemini returned an empty draft.")
    reply = _GROUPED_CITATION.sub(
        lambda match: "".join(f"[{ticket_id}]" for ticket_id in re.findall(_TICKET_ID, match[0])),
        reply,
    )

    return {
        "status": result.status,
        "text": reply,
        "cited_ids": extract_citation_ids(reply),
        "language": reply_language,
        "for_human_review": for_human_review,
        "model": config.LLM_MODEL,
    }


def _smoke() -> None:
    """Verify the configured Gemini model on synthetic English and German tickets."""
    import json
    from pathlib import Path
    from time import perf_counter

    from agent.citations import validate_citations

    fixture_path = (
        Path(__file__).resolve().parents[1] / "shared" / "fixtures" / "mock_triage_response.json"
    )
    precedents = json.loads(fixture_path.read_text(encoding="utf-8"))["precedents"]
    allowed_ids = {precedent["ticket_id"] for precedent in precedents}
    tickets = {
        "en": "Our branch offices cannot connect to the VPN. The client reports error 809.",
        "de": "Unsere Niederlassungen können sich nicht per VPN verbinden. Der Client meldet Fehler 809.",
    }

    try:
        for language, ticket in tickets.items():
            start = perf_counter()
            draft = generate_draft(ticket, language, precedents, for_human_review=True)
            elapsed = perf_counter() - start
            problems = validate_citations(
                draft["text"],
                draft["cited_ids"],
                allowed_ids,
                status=draft["status"],
                precedent_answers=(
                    precedent["answer"][:MAX_RESOLUTION_CHARS] for precedent in precedents
                ),
            )
            if draft["status"] != "OK" or problems:
                raise DraftError(f"{language}: smoke test did not return a valid cited draft.")
            print(
                f"{language}: {elapsed:.2f} s, {_word_count(draft['text'])} words, "
                f"{' '.join(draft['cited_ids'])}"
            )
            print(draft["text"])
            if elapsed >= 10:
                raise DraftError(f"{language}: draft took {elapsed:.2f} s, above the 10 s target.")
    except DraftError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    _smoke()
