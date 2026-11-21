# Data, Split and Leakage Rules

Breaking these rules can disqualify the team (brief, section 7). Every agent must follow them exactly.

## 1. Source

- Dataset: Hugging Face `Tobi-Bueck/customer-support-tickets`, licence CC-BY-NC-4.0
- File: `aa_dataset-tickets-multi-lang-5-2-50-version.csv` (the brief's recommended file)
- Download it with `huggingface_hub`, **not** `load_dataset(...)`. The repo has several CSVs, and `load_dataset` may load more than one of them.

```python
from huggingface_hub import hf_hub_download
path = hf_hub_download(
    repo_id="Tobi-Bueck/customer-support-tickets",
    filename="aa_dataset-tickets-multi-lang-5-2-50-version.csv",
    repo_type="dataset",
    local_dir="data/raw",
)
```
If the filename changed, list the files with `huggingface_hub.list_repo_files("Tobi-Bueck/customer-support-tickets", repo_type="dataset")`. Pick the closest match and log the choice in the decision log in `docs/plan.md`.

## 2. The split (A1 owns `ml/make_split.py`, done by T+0:30)

Do the shuffle and ID assignment exactly as the brief's snippet does, so the ticket IDs are reproducible and judges can verify them:

```python
df = pd.read_csv(path)
df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
split_idx = int(len(df) * 0.8)
kb  = df.iloc[:split_idx].copy()    # knowledge base + training (80%)
test = df.iloc[split_idx:].copy()   # holdout (20%)

# validation slice inside the KB, used to tune classifiers and thresholds
val_ids = set(kb.sample(frac=0.10, random_state=7)["ticket_id"])
kb["is_val"] = kb["ticket_id"].isin(val_ids)
```

Clean-up applied to **both** frames before saving:
- `subject`: NaN becomes `""`. `body`: NaN becomes `""`. Then drop rows whose `body` is empty after stripping (log the count).
- Collect `tag_1`..`tag_8` into one `tags` list column (non-null values only).
- Keep non-en/de rows if the file has any. The multilingual embeddings handle them, and replies fall back to English.

## 3. Files (all in `data/`, which is gitignored)

| File | Columns | Who may read it |
|---|---|---|
| `data/raw/*.csv` | everything | `ml/make_split.py` only |
| `data/kb_train.parquet` | all columns + `ticket_id`, `tags`, `is_val` | everyone: training (A1), indexing (B1), tuning (A2) |
| `data/test_inputs.parquet` | `ticket_id`, `subject`, `body` **only** | `eval/run_eval.py` (to make predictions) |
| `data/test_labels.parquet` | `ticket_id`, `type`, `queue`, `priority`, `language` | `eval/run_eval.py` only, **after** all predictions are saved |

The test split's `answer` and `tags` columns are **never written to disk**.

`make_split.py` must print, and `eval/run_eval.py` must re-check, the following:
- row counts for KB / val / test
- `assert "answer" not in test_inputs.columns and "answer" not in test_labels.columns`
- `assert set(kb.ticket_id).isdisjoint(test_inputs.ticket_id)`
- **split fingerprint:** `hashlib.sha256(",".join(test_inputs.ticket_id).encode()).hexdigest()[:12]`. Everyone posts their fingerprint in the team chat at kickoff, and all five must match. `metrics.json` records it too.

## 4. What each split may be used for

| Use | KB (`is_val == False`) | KB val (`is_val == True`) | Test |
|---|---|---|---|
| Train classifier | ✅ | ❌ (A1 may retrain on all KB rows **after** tuning; log it) | ❌ |
| Tune thresholds / pick model | ❌ (biased) | ✅ | ❌ |
| Index in FAISS (all fields incl. `answer`) | ✅ | ✅ (exclude the ticket's own ID when tuning) | ❌ **never** |
| Show as precedents / send to LLM | ✅ | ✅ | ❌ |
| Report final metrics | ❌ | ❌ | ✅ only via `eval/run_eval.py` |

## 5. Hard rules for agents

1. Never open `data/test_labels.parquet` anywhere except the scoring step of `eval/run_eval.py`.
2. Never write code that reads the raw CSV after the split exists, except `ml/make_split.py`.
3. `agent/build_index.py` reads **only** `data/kb_train.parquet`. It asserts that no indexed `ticket_id` appears in `data/test_inputs.parquet`.
4. Never print or log test-set labels or answers, and never paste them into a prompt, a notebook output or a commit.
5. Do not tune any threshold, prompt or model choice by looking at test metrics. Tune on KB val, then run the test eval **once** at the end (rerunning after a bug fix is fine, but log it).
6. Demo tickets in `docs/demo-tickets.md` are hand-written. Never copy a test row into them.
7. KB text that goes to the LLM (precedent answers and bodies) goes through `mask_pii` at index time.

## 6. Data facts to fill in after EDA (A1, by T+0:45)

A1 writes these into `ml/EDA.md` and pastes the headline numbers here:

- Rows total / KB / val / test: _TBD_
- Language mix: _TBD_
- Null or empty subjects: _TBD_ %
- Class balance (`type`, `priority`, `queue` top 10): _TBD_
- High-priority Incidents in KB / val: _TBD_ (the test support is reported by `eval/run_eval.py`, not by EDA)
- Exact-duplicate bodies shared between KB and test: _TBD_. These are allowed by the rules, but report the count for transparency.
- Placeholder tokens already present in the data (for example `<name>`, `<tel_num>`): _TBD_
