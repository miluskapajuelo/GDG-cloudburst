"""Shared text builder used for training, indexing and inference."""
from __future__ import annotations

import math
from typing import Any


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    try:
        import pandas as pd  # optional: handles pd.NA / NaT

        if pd.isna(value):
            return ""
    except (ImportError, TypeError, ValueError):
        pass
    return str(value).strip()


def build_text(subject: str | None, body: str | None) -> str:
    """Return the subject and body joined with a blank line (empty subject is skipped).
    Strip whitespace. Treat NaN or None as "". Use the same function for training, indexing and inference."""
    s, b = _clean(subject), _clean(body)
    return "\n\n".join(part for part in (s, b) if part)


if __name__ == "__main__":
    assert build_text("Hello", "World") == "Hello\n\nWorld"
    assert build_text(None, "World") == "World"
    assert build_text(float("nan"), "World") == "World"
    assert build_text("", "World") == "World"
    assert build_text("   ", "  World \n") == "World"
    assert build_text("  Subj ", None) == "Subj"
    assert build_text(None, None) == ""
    print("shared.text OK")
