# Data

## Source

- **Dataset:** [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) (Hugging Face)
- **Author:** Tobi-Bueck (Hugging Face)
- **License:** [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Non-commercial use only, attribution required.

## Files

| File | Rows | Size | SHA-256 |
|---|---|---|---|
| `raw/aa_dataset-tickets-multi-lang-5-2-50-version.csv` | 28,587 | 26.0 MB | `f187c090e59581c2bbf3aa1377c8db4dd647464ecf2ae51bf8966e42e0ed6bc0` |

- Languages: `en` 16,338, `de` 12,249
- Rows with an empty subject: 3,838

Load this one CSV directly. Don't use `load_dataset("Tobi-Bueck/customer-support-tickets")`, which merges every CSV in the repo, including a 20k file that overlaps with this one. Duplicate tickets could then land in both the knowledge-base split and the holdout split.

```python
import pandas as pd
df = pd.read_csv("data/raw/aa_dataset-tickets-multi-lang-5-2-50-version.csv")
```

## Re-downloading

```bash
curl -L -o data/raw/aa_dataset-tickets-multi-lang-5-2-50-version.csv \
  https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/aa_dataset-tickets-multi-lang-5-2-50-version.csv
```
