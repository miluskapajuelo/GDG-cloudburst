# SentinelDesk

> Multilingual incident triage, escalation gate and grounded reply drafting for IT support (English and German).

<!-- OWNER: miluskapajuelo (Team C). Fill each TODO by T+4:30. Get the numbers from A2 and the architecture notes from B2. -->

## What it does

TODO (3 lines). The console screenshot goes here.

## Architecture

TODO: copy the diagram from [docs/plan.md](docs/plan.md) §3.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # add GEMINI_API_KEY

python -m ml.make_split           # download the dataset, 80/20 split (seed 42)
python -m ml.train                # train the triage classifier
python -m agent.build_index       # embed the KB split into FAISS
uvicorn api.main:app --port 8000  # API
cd web && npm install && npm run dev   # console at http://localhost:5173
```

TODO: verify these commands on a fresh clone (A1).

## Evaluation (20% holdout)

```bash
python -m eval.run_eval --llm-sample 40
```

TODO: metrics table from `eval/results/metrics.md` (macro-F1 per head, High-Priority Incident recall, escalation rate, latency, grounding) and the split fingerprint.

## Escalation policy

TODO: summary. Full rules: [docs/escalation-policy.md](docs/escalation-policy.md).

## Leakage controls

TODO: summary. Full rules: [docs/data-and-leakage.md](docs/data-and-leakage.md).

## Bonus features

- TODO: cross-lingual precedent matching
- TODO: burst / major-incident detection
- TODO: PII masking before the LLM call

## Limitations and next steps

TODO

## Team

| Member | Role |
|---|---|
| shaadqrsh | A1: data split, classifier |
| gbuitra | A2: API service, evaluation |
| Karanpatel3114 | B1: retrieval, language, PII, burst |
| prithvipoojari | B2: escalation gate, grounded drafting |
| miluskapajuelo | C: console, README, demo |

Dataset: [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) (CC-BY-NC-4.0).
