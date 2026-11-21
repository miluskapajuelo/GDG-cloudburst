# Team A: ML & Eval

| Member | Role | Owns |
|---|---|---|
| `shaadqrsh` | **A1**: data split, classifier, demo machine | `ml/`, `shared/text.py`, the kickoff scaffold |
| `gbuitra` | **A2**: API service, evaluation, metrics, threshold tuning | `api/`, `eval/` |

Read first: [contract.md](../contract.md), [data-and-leakage.md](../data-and-leakage.md), [escalation-policy.md](../escalation-policy.md) §5.

**Why this team matters.** The judges score this team's numbers: Macro-F1 and High-Priority Incident Recall on the holdout. Every judge request also goes through this team's API. Correctness and honesty come before cleverness.

---

## A1: `shaadqrsh`

Agent: work only on the tasks in this section, in order. Tick each box in the same commit as the work.

### A1.1 Kickoff scaffold on `main` (by T+0:20)
- [x] Create these packages, each with an empty `__init__.py`: `ml/`, `api/`, `eval/`, `agent/`, `shared/`. Create `eval/results/` with a `.gitkeep`.
- [x] Create `shared/text.py` with `build_text(subject, body)` exactly as in the contract. Include a `__main__` check for `None`, NaN, empty subject and whitespace.
- [x] Check that `requirements.txt`, `.gitignore` and `.env.example` exist (they come from the docs commit). Run `pip install -r requirements.txt` on your machine.
- [x] Push to `main` (the one allowed direct push). Ask the human to tell everyone to `git pull`.

**Done when:** a fresh clone gives you `python -c "import ml, api, eval, agent, shared"` without errors.

### A1.2 Split (by T+0:30)
- [x] Write `ml/make_split.py` exactly as specified in [data-and-leakage.md](../data-and-leakage.md) §2–3: download, shuffle (seed 42), assign `TKT-xxxxx` IDs, split 80/20, flag the 10% val slice (seed 7), clean up, and write the 3 parquet files.
- [x] Print the row counts and the **split fingerprint**. Ask the human to post the fingerprint in the team chat. All five machines must match.
- [x] Commit through a PR. Share the command with the team: `python -m ml.make_split`.

**Done when:** the 3 files exist, the asserts pass, and the fingerprint is posted.

### A1.3 Quick EDA (by T+0:45)
- [x] Write `python -m ml.eda`. It prints: language mix, null/empty subject %, class counts for `type`, `priority` and `queue` (KB only), the number of high-priority Incidents in KB and in val (test support is reported later by `eval/run_eval.py`; EDA never reads test labels), text length percentiles, the count of exact-duplicate bodies shared between KB and test, and any `<placeholder>` tokens found in body/answer.
- [x] Write the results to `ml/EDA.md`. Paste the headline numbers into §6 of `data-and-leakage.md` (an allowed edit for A1).

### A1.4 Classifier (by T+1:30)
- [x] `ml/train.py`:
  - Train only on rows of `data/kb_train.parquet` with `is_val == False`. Input text: `build_text(subject, body)`.
  - Features: one shared `FeatureUnion` of `TfidfVectorizer(analyzer="word", ngram_range=(1,2), min_df=2, sublinear_tf=True, max_features=200_000)` and `TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=3, sublinear_tf=True, max_features=300_000)`. Fit it once.
  - Heads: one `LogisticRegression(class_weight="balanced", max_iter=2000, C=4.0)` per target (`type`, `queue`, `priority`), using the `saga` or `liblinear` solver.
  - Evaluate on the val rows. Print macro-F1 and accuracy per head, and val HPI recall (predicted high **and** Incident, among true high Incidents).
  - Save one bundle to `artifacts/clf.joblib`: `{"vectorizer", "heads": {...}, "labels": {...}, "trained_on": "kb_fit", "version"}`. Also write `artifacts/labels.json`.
  - Write val probabilities to `artifacts/val_preds.parquet` (`ticket_id`, and per-head `probs` as columns). A2 uses them for threshold tuning.
- [x] `ml/predict.py`: `TriageClassifier.load()` and `.predict(text)` returning the contract shape (`label`, `confidence`, `probs` as plain Python floats).
- [x] `__main__` smoke test: predict on 3 hand-written tickets (one en, one de, one with an empty subject).

**Done when:** training takes under 5 minutes on a laptop, `predict` takes under 20 ms per ticket, and val metrics are printed and pasted into the PR description.

### A1.5 Integration 1 (T+2:00)
- [ ] Merge the A1 PR first (merge order: A1, A2, B1, B2, C).
- [ ] Your laptop is the **demo machine**: build `data/` and `artifacts/` there (the B1 index too), and host the checkpoint run.

### A1.6 Improve and calibrate (T+2:15–3:15)
- [ ] Compute the expected calibration error (ECE, 10 bins) on val per head. If ECE is above 0.08, wrap the heads in `CalibratedClassifierCV(method="sigmoid", cv=3)` and keep the change only if val macro-F1 does not drop.
- [ ] Try one cheap improvement and keep it only if val macro-F1 improves: tune `C` ∈ {1, 4, 10}, or add simple features (has_subject, body length bucket).
- [ ] **(optional)** Compare with logistic regression on B1's multilingual embeddings (`Retriever.embed`). Keep the winner. Record the comparison in `ml/EDA.md`.
- [ ] Never look at test metrics while making these choices.

### A1.7 Threshold tuning support (T+3:30)
- [ ] Make sure `artifacts/val_preds.parquet` is current. Pair with A2 on `eval/tune_thresholds.py` if needed.
- [ ] **(optional)** After thresholds are locked, retrain on all KB rows (fit + val) for the final model. Log it in the decision log.

### A1.8 Demo machine ready (by T+4:00)
- [ ] Fresh `git pull`, then: `make_split`, `train`, `build_index`, eval run, API, web. Follow the README word for word and report any README gaps to `miluskapajuelo`.
- [ ] Make the API warm up models at startup (A2 implements it, you verify): the first request after startup must take under 3 s, excluding the LLM.
- [ ] `.env` holds a working key. Test the `SENTINEL_LLM_MODEL` switch once.

### A1.9 Q&A prep (by T+4:30)
- [ ] Write 5 bullet points in `ml/EDA.md` under "Judge Q&A": why TF-IDF + LR, how leakage is prevented, why priority F1 is modest, how HPI recall is achieved (gate probabilities), and what we would do with more time.

---

## A2: Gustavo (`gbuitra`)

Agent: work only on the tasks in this section, in order. Tick each box in the same commit as the work.

### A2.0 Register yourself (first commit)
- [x] Replace `GUSTAVO_LOGIN` with your GitHub login everywhere it appears: `CLAUDE.md` (roster and Step 0 question), `docs/plan.md`, `README.md` (team table) and the table at the top of this file. Run `git grep GUSTAVO_LOGIN` to confirm none are left. This is an allowed edit for you.

### A2.1 API skeleton with mock mode (by T+0:30). Unblocks Team C.
- [x] `api/schemas.py`: Pydantic v2 models that mirror the contract response exactly (`TriageRequest`, `TriageResponse` and the nested models).
- [x] `api/main.py` (FastAPI):
  - Endpoints: `GET /health`, `GET /config`, `GET /metrics`, `POST /triage`, `POST /burst/reset`.
  - CORS for ports 5173 and 8501.
  - With `SENTINEL_MOCK=1`, `/triage` returns `shared/fixtures/mock_triage_response.json` with a fresh `request_id`, `"mock": true` and `input` filled from the request. No model loading.
- [x] Validation: an empty or whitespace `body` returns 422. A body over 8,000 chars is truncated and `input.truncated = true`.

**Done when:** `SENTINEL_MOCK=1 uvicorn api.main:app --port 8000` works, `curl -X POST localhost:8000/triage -H "content-type: application/json" -d '{"body":"test"}'` returns the fixture, and `miluskapajuelo` is told it is ready.

### A2.2 Service orchestrator (by T+1:15)
- [ ] `api/service.py`: `triage(subject, body, *, skip_llm=False)`. It follows the fixed order in contract §2 and times each stage with `time.perf_counter()` (integer ms).
- [ ] Load models once in a FastAPI lifespan handler: `TriageClassifier.load()`, `Retriever.load()`, `BurstDetector(...)`, `AgentPipeline(...)`. Run one warm-up `triage("warmup", "warm up", skip_llm=True)`.
- [ ] Progressive wiring: if a module is missing (`ImportError`) or its artifact is missing, fall back to a stub in `api/stubs.py` that returns contract-shaped data. `/health` reports which parts are real. Team A must never block on Team B.

### A2.3 Holdout evaluation script (by T+1:45, first full run at T+2:30)
- [ ] `eval/run_eval.py`. Flags: `--limit N`, `--llm-sample N` (default 0), `--out eval/results`.
  1. Re-check the leakage asserts from data-and-leakage §3. Compute the split fingerprint.
  2. Load **only** `test_inputs.parquet`. Call `api.service.triage(subject, body, skip_llm=True)` for every row (in-process: same code path as the demo). Save the predictions, escalation status, reason codes, detected language and per-stage latency to `eval/results/test_predictions.parquet` (gitignored).
  3. **Only then** load `test_labels.parquet` and score:
     - macro-F1, weighted-F1 and accuracy per head, plus a per-class report and confusion matrix per head
     - **HPI classifier recall**: among true (priority=high and type=Incident), the fraction predicted as high **and** Incident
     - **HPI escalation recall**: among the same tickets, the fraction with `status == ESCALATE` (any route)
     - overall escalation rate, and counts per reason code
     - language detection accuracy against the `language` label
     - latency p50/p95 per stage, and total (skip_llm)
  4. Write `eval/results/metrics.json` (shape below) and `eval/results/metrics.md` (human-readable tables). Commit both.
- [ ] Batch the classifier/embedding work if the full test run takes over 10 minutes, but keep the per-ticket latency numbers honest: measure them on a 300-ticket sample through `triage()`.

### A2.4 Integration 1 (T+2:00)
- [ ] Wire the real classifier and retriever into `service.py` (replace stubs). Merge after A1.

### A2.5 LLM sample evaluation (by T+3:15)
- [ ] `--llm-sample 40`: a stratified sample of test inputs (at least 10 predicted high/Incident; mixed en/de), run with `skip_llm=False`. Measure:
  - `generate` latency p50/p95 and total latency p50/p95
  - citation validity rate (no `CITATION_CHECK_FAILED`)
  - the fraction of OK drafts with at least 1 citation
  - `INSUFFICIENT_EVIDENCE` rate and `LLM_UNAVAILABLE` rate
  - reply-language match rate (detect the language of `draft.text`, compare with `language.reply_language`)
- [ ] Save the drafts to `eval/results/llm_samples.jsonl`: `ticket_id`, predictions, escalation, draft. **No test labels and no test answers.**
- [ ] LLM calls cost money and time. Run the sample at most 3 times in total.

### A2.6 `GET /metrics` and the `metrics.json` shape
```json
{
  "generated_at": "2026-11-21T15:30:00Z",
  "split_fingerprint": "ab12cd34ef56",
  "n_test": 0,
  "classifier": {
    "type":     { "macro_f1": 0.0, "weighted_f1": 0.0, "accuracy": 0.0 },
    "queue":    { "macro_f1": 0.0, "weighted_f1": 0.0, "accuracy": 0.0 },
    "priority": { "macro_f1": 0.0, "weighted_f1": 0.0, "accuracy": 0.0 }
  },
  "high_priority_incident": { "support": 0, "classifier_recall": 0.0, "escalation_recall": 0.0 },
  "escalation": { "rate": 0.0, "reason_counts": { "HIGH_PRIORITY_INCIDENT": 0 } },
  "language_detection_accuracy": 0.0,
  "latency_ms": {
    "skip_llm": { "p50": 0, "p95": 0, "n": 0 },
    "with_llm": { "p50": 0, "p95": 0, "generate_p50": 0, "generate_p95": 0, "n": 0 }
  },
  "grounding": { "n": 0, "citation_valid_rate": 0.0, "draft_with_citation_rate": 0.0, "insufficient_evidence_rate": 0.0, "llm_unavailable_rate": 0.0, "reply_language_match_rate": 0.0 },
  "thresholds": { "T_SIM": 0.55 }
}
```

### A2.7 Threshold tuning (T+3:30–3:50)
- [ ] `eval/tune_thresholds.py`, on **KB val rows only**, following [escalation-policy.md](../escalation-policy.md) §5:
  - Use `artifacts/val_preds.parquet` for the classifier probabilities and `Retriever.search(exclude_ids={ticket_id})` for similarities.
  - Sweep `T_HIGH_PRIORITY_P`, `T_INCIDENT_P`, the `T_CONF_*` values and `T_SIM`.
  - Report HPI escalation recall, escalation rate and NO_PRECEDENT rate for each setting.
- [ ] Write `eval/results/threshold_sweep.md` with a recommended row. Send it to `prithvipoojari`, who updates `agent/config.py`.

### A2.8 Red-team runner (by T+3:50)
- [ ] `eval/run_redteam.py`: run every ticket in `shared/fixtures/demo_tickets.json` through `triage()` with the LLM on. Compare against `expected_status` / `expected_reason_codes`. Write `eval/results/redteam.md` (a pass/fail table, plus the draft text for failures).
- [ ] Before the run, call `/burst/reset` (or `BurstDetector.reset()`), and run the burst tickets in order.

### A2.9 Final eval and handoff (T+4:00–4:15)
- [ ] After the freeze, run the final `python -m eval.run_eval --llm-sample 40` on the demo machine. Commit the `metrics.*` files.
- [ ] Send `miluskapajuelo` the metrics table and the exact eval commands for the README.
