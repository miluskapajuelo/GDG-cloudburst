# Running SentinelDesk end to end

Owner: A2 (`gbuitra`). This is the step-by-step for any team member, and for the demo machine (A1, `shaadqrsh`).
Run every command from the **repo root** unless a step says `cd web`.

| Step | What | Time |
|---|---|---|
| 1 | Python env + packages | 5–15 min (torch is large) |
| 2 | `.env` with the Gemini key | 1 min |
| 3 | Data split, classifier, index | ~1 min split, <5 min train, the index build is the slow one |
| 4 | API | seconds (models warm up at startup) |
| 5 | Web console | 1–2 min |
| 6 | Evaluation (A2) | thresholds → holdout + LLM sample → red-team |

---

## 1. Python environment

Use **Python 3.13 or 3.14**. Python 3.9 fails with `Unable to evaluate type annotation 'str | None'`.

```bash
python3 --version                      # must be 3.13+; on macOS with pyenv this is often 3.9
# if it is too old, call a newer interpreter by path, e.g. Homebrew:
#   /opt/homebrew/bin/python3.13 -m venv .venv
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python --version                       # check again inside the venv
pip install -r requirements.txt
```

Always start tools through the venv's Python (`python -m uvicorn`, `python -m pytest`). A bare `uvicorn` can pick up a global
install that does not have the project packages (`ModuleNotFoundError: No module named 'fastapi'`).

## 2. Secrets

```bash
cp .env.example .env
# edit .env: GEMINI_API_KEY=...   (never commit .env, never paste the key in chat)
```

Without a key everything still runs; drafts come back as `LLM_UNAVAILABLE` and the console still shows triage and precedents.

## 3. Build data and models (once per machine)

```bash
python -m ml.make_split        # data/kb_train.parquet, data/test_inputs.parquet, data/test_labels.parquet
python -m ml.train             # artifacts/clf.joblib, labels.json, val_preds.parquet
python -m agent.build_index    # artifacts/kb.faiss, artifacts/kb_meta.parquet
```

Check the split fingerprint printed by `make_split`: it must be **`5a2ede85f9fb`** on every machine
(28,587 rows: KB 22,869 incl. val 2,287, test 5,718). If it differs, stop and tell A1.

Nothing in `data/` or `artifacts/` is ever committed (`.gitignore`).

## 4. Start the API

```bash
python -m uvicorn api.main:app --port 8000
```

Check it at **http://127.0.0.1:8000/health**. For the full demo every component must say `"real"`:

```json
{"status": "ok", "mock": false, "classifier_loaded": true, "index_size": 22869, "llm_configured": true, ...}
```

If a component says `"stub"`, its artifact or module is missing: redo step 3, or `git pull` for the missing module.
Interactive API docs: http://127.0.0.1:8000/docs

**Mock mode** (frontend work without models; every ticket returns the fixture):

```bash
SENTINEL_MOCK=1 python -m uvicorn api.main:app --port 8000      # Windows PowerShell: $env:SENTINEL_MOCK=1; python -m uvicorn ...
```

## 5. Start the web console

```bash
cd web
cp .env.example .env.local
# in web/.env.local:  VITE_API_URL=http://127.0.0.1:8000
npm install
npm run dev                    # http://localhost:5173 (must be port 5173: the API's CORS list expects it)
```

Use `127.0.0.1:8000`, not `localhost:8000`, in `VITE_API_URL`: on some laptops another local app also listens on
`localhost:8000` and the console then talks to the wrong service. `VITE_OFFLINE=1` runs the console on built-in fixtures
without any API.

## 6. Evaluation (A2), in this order

Run with the API stopped or running; the scripts call `api.service` in-process (the same code path as the demo).

```bash
# 6a. Threshold sweep on KB validation rows only (never test). Send the report to B2 (prithvipoojari).
python -m eval.tune_thresholds
#     -> eval/results/threshold_sweep.md / .json   (B2 copies the recommended row into agent/config.py)

# 6b. After B2 updates agent/config.py: holdout metrics + LLM sample (at most 3 LLM-sample runs in total)
python -m eval.run_eval --llm-sample 40
#     -> eval/results/metrics.md / .json (served by GET /metrics), llm_samples.jsonl
#     quick check without the LLM:  python -m eval.run_eval --limit 200

# 6c. Red-team: every ticket in shared/fixtures/demo_tickets.json, LLM on
python -m eval.run_redteam
#     -> eval/results/redteam.md / .json
#     against a running server instead:  python -m eval.run_redteam --url http://127.0.0.1:8000
```

Commit `metrics.md`, `metrics.json`, `threshold_sweep.md`, `threshold_sweep.json` and `redteam.md`.
`test_predictions.parquet` is gitignored and stays local.

Leakage rules still apply: only `eval/run_eval.py` reads `data/test_labels.parquet`, and only after predictions are written.

## 7. Tests (each file < 30 s, no network)

```bash
python -m pytest tests -q
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Unable to evaluate type annotation 'str \| None'` | venv built with Python 3.9 | `rm -rf .venv`, recreate with Python 3.13+ (step 1) |
| `No module named 'fastapi'` from `/opt/homebrew/bin/uvicorn` | a global uvicorn ran instead of the venv's | `source .venv/bin/activate` and use `python -m uvicorn` |
| `No module named 'numpy'` in eval or red-team | only the mock-mode packages are installed | `pip install -r requirements.txt` |
| `/health` shows `"stub"` components | artifacts not built or module not merged yet | step 3, `git pull origin main` |
| Console shows a different app / Swagger "ECU Tuning Studio" | another service on `localhost:8000` | `VITE_API_URL=http://127.0.0.1:8000` |
| `GET /metrics` returns 404 | eval has not run yet | step 6b |
| Eval warns "the LLM sample made no LLM calls" | no `GEMINI_API_KEY`, or PII/pipeline still stubs | step 2, check `/health` |
| Eval refuses: "LLM sample already ran 3 times" | the A2.5 run cap | intended; `--force-llm-sample` only if the team agrees |
| Split fingerprint is not `5a2ede85f9fb` | different data file or code version | `git pull`, rerun `make_split`, tell A1 |
