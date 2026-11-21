# SentinelDesk: Project Plan

**Duration:** 5 hours from kickoff. `T+h:mm` means time since kickoff.
**Goal:** a working live console that judges can paste unseen tickets into. It must show triage, the escalation decision, cited precedents and a grounded draft. It must be backed by honest holdout metrics.

## 1. What we are scored on (from the brief)

| Required deliverable | Owner | Where |
|---|---|---|
| Multi-task triage (`type`, `queue`, `priority` + confidence) | A1 | `ml/` |
| Holdout Macro-F1 + High-Priority Incident Recall | A2 | `eval/` |
| `/triage` HTTP service + latency timing | A2 | `api/` |
| Escalation and safety gate with explicit rules | B2 | `agent/gate.py` |
| Top-k retrieval of past tickets from the KB split only | B1 | `agent/retrieve.py` |
| Grounded draft in en/de that cites ticket IDs and refuses to fabricate | B2 | `agent/draft.py` |
| Live console: predictions, confidence, latency, badge, precedents, draft | C | `web/` |
| README, `requirements.txt`, eval script, 5-minute demo | C (README, demo), A2 (eval) | root |
| Bonus: cross-lingual retrieval | B1 (multilingual embeddings) | `agent/retrieve.py` |
| Bonus: burst / major-incident banner | B1 (logic), C (UI) | `agent/burst.py`, `web/` |
| Bonus: PII masking before the LLM call | B1 | `agent/pii.py` |

## 2. Team roster

| Team | Members | Owns |
|---|---|---|
| **A: ML & Eval** | `shaadqrsh` (A1: data, classifier, demo machine), `gbuitra` (A2: API service, eval) | `ml/`, `api/`, `eval/`, `shared/text.py` |
| **B: Agent** | `Karanpatel3114` (B1: retrieval, language, PII, burst), `prithvipoojari` (B2: gate, drafting, citations, pipeline) | `agent/` |
| **C: Frontend** | `miluskapajuelo` | `web/`, `README.md`, `docs/demo-script.md` |

The source of truth for who does what is the roster in [CLAUDE.md](../CLAUDE.md).

## 3. Architecture

```
            ┌──────────────── web/ (Team C) ────────────────┐
            │ Vite + React console  ── POST /triage ──┐     │
            └─────────────────────────────────────────┼─────┘
                                                      ▼
┌──────────────────────────── api/ (Team A) ───────────────────────────────┐
│ 1 build_text(subject, body)              shared/text.py                  │
│ 2 mask_pii(text)                          agent/pii.py        (B1)       │
│ 3 detect_language(masked)                 agent/lang.py       (B1)       │
│ 4 TriageClassifier.predict(masked)        ml/predict.py       (A)        │
│ 5 AgentPipeline.run(masked, lang, preds)  agent/pipeline.py   (B2)       │
│     ├─ Retriever.embed + search (top-5)   agent/retrieve.py   (B1)       │
│     ├─ BurstDetector.observe              agent/burst.py      (B1)       │
│     ├─ pre_draft_gate                     agent/gate.py       (B2)       │
│     ├─ generate_draft → Gemini API        agent/draft.py      (B2)       │
│     ├─ validate_citations                 agent/citations.py  (B2)       │
│     └─ finalize_escalation                agent/gate.py       (B2)       │
│ 6 assemble response + latency_ms          api/service.py      (A)        │
└──────────────────────────────────────────────────────────────────────────┘
   artifacts/clf.joblib (A)     artifacts/kb.faiss + kb_meta.parquet (B1)
   eval/run_eval.py → eval/results/metrics.{json,md} → GET /metrics → console KPI strip
```

## 4. Stack decisions (locked at kickoff)

| Concern | Decision | Why |
|---|---|---|
| Language | Python 3.14 backend, TypeScript frontend | Team familiarity, speed |
| Classifier | TF-IDF (word 1–2 grams + char 3–5 grams) → 3 logistic regression heads | Trains in seconds, strong baseline, good probabilities |
| Embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-dim, normalised) | Fast on CPU, en↔de cross-lingual retrieval included |
| Vector store | FAISS `IndexFlatIP` (exact cosine) | About 50k vectors: exact search takes milliseconds, no tuning |
| Language detection | `lingua-language-detector` | Accurate on short text |
| LLM | Google Gemini via the `google-genai` Python SDK. Default `gemini-3.5-flash-lite` (stable, free tier), set by `SENTINEL_LLM_MODEL` | Free, fast, stable. If grounding or German quality is weak, switch the env var to `gemini-3.8-flash` (stable, also free tier). Confirm the model supports `response_schema` with a test call at kickoff |
| API | FastAPI + Uvicorn on port 8000 | Typed, quick |
| Frontend | Vite + React + TypeScript + Tailwind on port 5173. Fallback: Streamlit `web/app.py` on 8501 | C decides at T+0:15 and logs it below |

## 5. Timeline and checkpoints

| Time | Phase | Exit criteria |
|---|---|---|
| **T+0:00–0:30** | Kickoff | Repo scaffold on `main`. Everyone installed. Split files exist locally. Contract confirmed by all 5. `SENTINEL_MOCK=1` API serves the fixture. |
| T+0:30–2:00 | Parallel build against mocks | Each team's required "by T+2:00" tasks done (see task files) |
| **T+2:00** | **Integration 1** (15 min, all hands) | `main` has real classifier + real retrieval behind `/triage` (draft may still be stubbed). The console calls the real API. |
| T+2:15–3:15 | Grounding and polish | Real LLM drafts with citations, gate finished, PII + language live, UI complete |
| **T+3:15** | **Integration 2** (15 min, all hands) | Full end-to-end path. All tickets in `docs/demo-tickets.md` run without crashing. Red-team results reviewed. |
| T+3:30–4:00 | Eval + bonuses | `eval/results/metrics.md` committed. Thresholds tuned on validation. Burst banner works. |
| **T+4:00** | **Feature freeze** | Only bug fixes, README and demo prep after this |
| T+4:00–5:00 | Demo prep | README final, demo rehearsed twice, backup screen recording saved, a clean demo machine running |

**Demo machine:** the laptop of `shaadqrsh` (A1) runs the final stack. It must have `data/` and `artifacts/` built from the same split.

## 6. Integration checkpoint procedure

1. Each owner merges their PR to `main`, in this order: A1 (ml), then A2 (api), then B1, then B2, then C.
2. On the demo machine: `git pull`, `pip install -r requirements.txt`, rebuild artifacts if needed, start the API and the web app.
3. Run all presets in `docs/demo-tickets.md` through the console. Log any failure as a GitHub issue assigned to the owner.
4. Agree on the next 60 minutes. Note anything descoped in the decision log below.

## 7. Risks and fallbacks

| Risk | Fallback |
|---|---|
| LLM latency > 10 s or API down | Already on the fastest free model (`gemini-3.5-flash-lite`); lower `max_output_tokens` or trim precedent text. If the API is down, the gate returns `LLM_UNAVAILABLE` and the console still shows triage + precedents. |
| Index build too slow on a laptop | Build once on the fastest machine and share `artifacts/` via USB or a drive link (never git). Use the 20k file only as a last resort, and log it. |
| React UI behind schedule at T+2:00 | C switches to Streamlit `web/app.py` (same contract). |
| Classifier priority F1 is low (noisy labels) | Expected. Report honestly. Recall on high-priority incidents comes from the gate's probability thresholds, not from argmax. |
| Merge conflicts | Folder ownership. Shared files have sectioned edits. Contract changes go through the PR process. |

## 8. Decision log

Add one line per decision: `T+h:mm — decision — who`.

- T+0:00 — Plan adopted: 3 teams. A: ML & Eval ×2 (shaadqrsh, Gustavo). B: Agent ×2 (Karanpatel3114, prithvipoojari). C: Frontend ×1 (miluskapajuelo) — all
- T+0:15 — C.1 stack: Vite 8 + React 19 + TypeScript + Tailwind v4 (`@tailwindcss/vite`), lucide-react icons, oxlint. Not Streamlit. Prototype currently lives in `ui/`; it moves to `web/` (the roster folder) in C.2 — miluskapajuelo
- T+2:07 — BURST_SIM 0.75→0.65 (B1: 0% false banners at 10 tickets with the rare-term rule; demo-12 activates) — prithvipoojari
