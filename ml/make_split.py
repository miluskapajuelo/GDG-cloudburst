"""Build the KB / val / test split. Run: python -m ml.make_split

Follows docs/data-and-leakage.md sections 2-3 exactly.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

REPO_ID = "Tobi-Bueck/customer-support-tickets"
FILENAME = "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
LABEL_COLS = ["type", "queue", "priority", "language"]


def get_raw_csv() -> Path:
    # The CSV is committed at data/<FILENAME>; data/raw/ is the hf_hub_download location.
    for local in (DATA_DIR / FILENAME, RAW_DIR / FILENAME):
        if local.exists():
            return local
    from huggingface_hub import hf_hub_download

    return Path(
        hf_hub_download(repo_id=REPO_ID, filename=FILENAME, repo_type="dataset", local_dir=str(RAW_DIR))
    )


def clean(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["subject"] = frame["subject"].fillna("").astype(str)
    frame["body"] = frame["body"].fillna("").astype(str)
    empty = frame["body"].str.strip() == ""
    print(f"{name}: dropped {int(empty.sum())} rows with empty body")
    frame = frame.loc[~empty].copy()
    tag_cols = [c for c in frame.columns if c.startswith("tag_")]
    frame["tags"] = frame[tag_cols].apply(lambda r: [str(v) for v in r if pd.notna(v)], axis=1)
    return frame.drop(columns=tag_cols)


def fingerprint(ticket_ids: pd.Series) -> str:
    return hashlib.sha256(",".join(ticket_ids).encode()).hexdigest()[:12]


def main() -> None:
    path = get_raw_csv()
    df = pd.read_csv(path)
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    split_idx = int(len(df) * 0.8)
    kb = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:].copy()

    val_ids = set(kb.sample(frac=0.10, random_state=7)["ticket_id"])
    kb["is_val"] = kb["ticket_id"].isin(val_ids)

    kb = clean(kb, "kb")
    test = clean(test, "test")

    test_inputs = test[["ticket_id", "subject", "body"]].reset_index(drop=True)
    test_labels = test[["ticket_id", *LABEL_COLS]].reset_index(drop=True)

    assert "answer" not in test_inputs.columns and "answer" not in test_labels.columns
    assert set(kb.ticket_id).isdisjoint(test_inputs.ticket_id)

    DATA_DIR.mkdir(exist_ok=True)
    kb.reset_index(drop=True).to_parquet(DATA_DIR / "kb_train.parquet", index=False)
    test_inputs.to_parquet(DATA_DIR / "test_inputs.parquet", index=False)
    test_labels.to_parquet(DATA_DIR / "test_labels.parquet", index=False)

    n_val = int(kb["is_val"].sum())
    print(f"rows total={len(df)}  kb={len(kb)} (fit={len(kb) - n_val}, val={n_val})  test={len(test_inputs)}")
    print(f"split fingerprint: {fingerprint(test_inputs['ticket_id'])}")


if __name__ == "__main__":
    main()
