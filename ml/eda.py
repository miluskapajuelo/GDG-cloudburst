"""Quick EDA. Run: python -m ml.eda   (writes ml/EDA.md)

Reads data/kb_train.parquet and data/test_inputs.parquet ONLY. Never reads test labels.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from shared.text import build_text

DATA = Path("data")
OUT = Path("ml/EDA.md")
PLACEHOLDER = re.compile(r"<[a-z_]+>")


def counts(series: pd.Series, top: int | None = None) -> str:
    vc = series.value_counts()
    if top:
        vc = vc.head(top)
    total = len(series)
    return "\n".join(f"| {k} | {v} | {v / total:.1%} |" for k, v in vc.items())


def main() -> None:
    kb = pd.read_parquet(DATA / "kb_train.parquet")
    test = pd.read_parquet(DATA / "test_inputs.parquet")
    val = kb[kb["is_val"]]
    lines: list[str] = ["# EDA (KB only; test inputs used only for duplicate/length checks)", ""]

    def section(title: str, body: str) -> None:
        lines.extend([f"## {title}", "", body, ""])
        print(f"\n== {title} ==\n{body}")

    section("Rows", f"KB={len(kb)} (fit={len(kb) - len(val)}, val={len(val)}), test={len(test)}")

    section("Language mix (KB)", "| language | n | % |\n|---|---|---|\n" + counts(kb["language"]))

    empty_kb = (kb["subject"].str.strip() == "").mean()
    empty_test = (test["subject"].str.strip() == "").mean()
    section("Empty subject", f"KB: {empty_kb:.1%}, test inputs: {empty_test:.1%}")

    for col, top in (("type", None), ("priority", None), ("queue", 10)):
        hdr = f"Class counts: {col} (KB" + (", top 10)" if top else ")")
        section(hdr, f"| {col} | n | % |\n|---|---|---|\n" + counts(kb[col], top))
    section("Queue cardinality", f"{kb['queue'].nunique()} queues in KB")

    hpi = (kb["priority"] == "high") & (kb["type"] == "Incident")
    section(
        "High-priority Incidents",
        f"KB total: {int(hpi.sum())} ({hpi.mean():.1%}); fit: {int(hpi[~kb['is_val']].sum())}; "
        f"val: {int(hpi[kb['is_val']].sum())}",
    )

    lengths = pd.Series([len(build_text(s, b)) for s, b in zip(kb["subject"], kb["body"])])
    q = lengths.quantile([0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).astype(int)
    section(
        "Text length (chars, build_text, KB)",
        " ".join(f"p{int(k * 100)}={v}" for k, v in q.items()) + f" max={lengths.max()}",
    )

    kb_bodies = set(kb["body"].str.strip())
    dup = test["body"].str.strip().isin(kb_bodies)
    section("Exact-duplicate bodies KB vs test", f"{int(dup.sum())} test bodies also appear in KB ({dup.mean():.2%})")

    tok = pd.Series(
        [t for txt in pd.concat([kb["body"], kb["answer"].fillna("")]) for t in PLACEHOLDER.findall(txt)]
    )
    section(
        "Placeholder tokens in KB body/answer",
        "| token | n |\n|---|---|\n" + "\n".join(f"| `{k}` | {v} |" for k, v in tok.value_counts().head(15).items()),
    )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
