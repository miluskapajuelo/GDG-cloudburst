# Team C: Frontend (Live Triage Console, README, Demo)

| Member | Role | Owns |
|---|---|---|
| `miluskapajuelo` | Console UI, README, demo script | `web/`, `README.md`, `docs/demo-script.md` |

Read first: [contract.md](../contract.md) §1 (every field you render), [escalation-policy.md](../escalation-policy.md) §1 (badge and route meanings), [demo-tickets.md](../demo-tickets.md).

**Why this matters.** The judges see only the console. They will paste unseen tickets during Q&A. The console must never crash, must make the escalation decision obvious at a glance, and must show *why* (reasons, precedents, citations).

Agent: work only on the tasks below, in order. Tick each box in the same commit as the work. Until A2 says the real API is up, build against mock mode: `SENTINEL_MOCK=1 uvicorn api.main:app --port 8000`. If that is not ready yet, import `shared/fixtures/mock_triage_response.json` directly.

> **Mock mode is ready (A2.1 merged in PR #8).** Run `git pull origin main` first. Start the API in mock mode:
> - macOS/Linux/Git Bash: `SENTINEL_MOCK=1 uvicorn api.main:app --port 8000`
> - Windows PowerShell: `$env:SENTINEL_MOCK="1"; uvicorn api.main:app --port 8000`
>
> In mock mode, `GET /health` returns `"mock": true`. `POST /triage` returns the contract-shaped fixture with a fresh `request_id` and `input` filled from your request. An empty `body` returns 422 (show a validation message, do not crash). CORS allows `http://localhost:5173`. Point `VITE_API_URL` at `http://localhost:8000` and build every panel against this response. Switch to the real API only when A2 says it is up. The response shape does not change.

If the `frontend-design` skill is available, load it before building the UI.

**Design rules:** read [design-rules.md](../design-rules.md) before writing any UI code. It covers drafts, palette, type, layout and copy, and how they override the layout sketch below.

---

### C.1 Stack decision (by T+0:15)
- [x] The default is **Vite + React + TypeScript + Tailwind** in `web/`. Choose **Streamlit** (`web/app.py`, one file) only if the human prefers Python or is not comfortable with React. Log the choice in the decision log in `docs/plan.md`.
- The rest of this file assumes React. For Streamlit, build the same sections with `st.columns`, `st.metric`, `st.progress`, `st.dataframe` and `st.expander`.

### C.2 Scaffold (by T+0:30)
- [x] Run `npm create vite@latest web -- --template react-ts`, add Tailwind, and add `web/.env.local` with `VITE_API_URL=http://localhost:8000`. Commit a `web/.env.example`.
- [x] In `vite.config.ts`, set `server.fs.allow: [".."]` so you can import `../shared/fixtures/*.json`.
- [x] `web/src/types.ts`: TypeScript types that mirror the contract response exactly. Copy the field names; do not rename them.
- [x] `web/src/api.ts`: `triage(subject, body)`, `health()`, `config()`, `metrics()` and `resetBurst()`, with a 60 s timeout and typed errors.

**Done when:** the page renders the mock fixture with no API running.

### C.3 Input panel (by T+1:15)
- [x] Inputs: Subject (optional, single line), Body (required, multi-line, at least 8 rows), and a **Triage** button. Ctrl+Enter submits. Disable the button while the body is empty or a request is in flight.
- [x] A **Presets** dropdown loaded from `shared/fixtures/demo_tickets.json`. Selecting one fills Subject and Body without submitting. Show the `title` and the `purpose`.
- [x] Show a character count, and a "subject empty: fine" hint when the subject is blank. This shows judges that null subjects are handled.

### C.4 Results view (by T+2:00, then connect to the real API at Integration 1)
Layout, wide screen (projector-friendly, base font 16px or larger):
```
┌───────────────────────────────────────────────────────────────────────────┐
│ [BURST BANNER: Major incident: 4 similar tickets in 15 min: "VPN …"]      │ (only when burst.active)
├──────────────────────────┬────────────────────────────────────────────────┤
│ INPUT PANEL (C.3)        │ ESCALATION BADGE (large) + reasons list        │
│                          │ ┌ type ┐ ┌ queue ┐ ┌ priority ┐  lang · PII    │
│ History (last 10)        │ │label │ │label  │ │label     │  chips         │
│                          │ │conf ▓│ │conf ▓ │ │conf ▓    │                │
│                          │ └──────┘ └───────┘ └──────────┘                │
│                          │ LATENCY: stacked bar per stage + total ms      │
│                          │ DRAFT panel (citations as chips)               │
│                          │ PRECEDENTS table                               │
├──────────────────────────┴────────────────────────────────────────────────┤
│ Holdout metrics strip (GET /metrics) · API health dot · model name        │
└───────────────────────────────────────────────────────────────────────────┘
```
- [x] **Escalation badge** (the most prominent element on the page). Use `escalation.badge` text and colour it by route: `null`/AUTO_DRAFT is green, `HUMAN_REVIEW` is amber, `ON_CALL` is red. Below it, list each reason as `CODE: message`.
- [x] **Prediction cards**: one card each for type, queue and priority, showing the label, a confidence bar with its percentage, and a hover or expander with the top 3 `probs`.
- [x] **Chips**: detected language (`DE`/`EN` and the confidence), and PII (for example "PII masked: 1 email, 1 IP"; hidden when there are no counts).
- [x] **Latency**: a stacked horizontal bar of `pii`, `language`, `classify`, `retrieve`, `gate` and `generate`, with `total` in ms. Label the bar "end-to-end latency".
- [x] **Draft panel**:
  - Render `draft.text` with every `[TKT-xxxxx]` turned into a clickable chip. Clicking a chip scrolls to the matching precedent row and highlights it.
  - Show a "For human review: do not send" ribbon when `for_human_review` is true. Show an "Insufficient evidence: holding reply" tag when `status == INSUFFICIENT_EVIDENCE`.
  - Add a Copy button and show the model name in small text.
  - When `draft` is `null`, show "No draft generated" with the reason (from the reason codes).
- [x] **Precedents table**: `ticket_id`, a similarity bar with its number, language, queue/type/priority (small), and `answer_snippet` with an expander for the full `answer`. Show "Cross-lingual" when the precedent's language differs from the ticket's.
- [x] **States**: a skeleton while loading. For an error, show a toast with the message and keep the last result visible. If the API is down, the health dot turns red with "API offline". The UI must not crash on missing optional fields.

### C.5 Burst demo (by T+2:45)
- [x] Show the burst banner when `burst.active`: red, full width, with `cluster_size`, `window_minutes` and `label`.
- [x] Add a **Run burst scenario** button: it calls `POST /burst/reset`, then sends the presets tagged `"burst": true` one after another (with a 1 s gap), and shows each result as it arrives.
- [x] Add a **Reset burst** button.

### C.6 Context widgets (by T+3:15)
- [x] Holdout metrics strip from `GET /metrics`: macro-F1 for type, queue and priority, HPI escalation recall, and p50 latency. On 404, show "Eval not run yet".
- [x] A thresholds popover from `GET /config`, so a judge asking "what is your threshold?" can be answered in one click.
- [x] A history sidebar: the last 10 results in memory, each showing the badge colour, subject or the first 40 chars, and the time. Clicking one shows that result again.

### C.7 Polish and robustness (T+3:15–4:00)
- [x] Test with: an empty subject, a 7,000-char body, German umlauts, a body with HTML-like `<script>` text (render it as text; never use `dangerouslySetInnerHTML`), the API returning 422, and the API down.
- [x] Check readability at 1280×720 (projector). Use high contrast. Do not use colour alone for meaning: the badge text matters.

### C.8 README.md (draft by T+3:30, final by T+4:30)
Fill in the skeleton `README.md` (already in the repo). Get the numbers from A2 and the architecture notes from B2. Required sections:
- [x] What it does (3 lines) and a screenshot of the console
- [x] Architecture (copy the diagram from `docs/plan.md`)
- [ ] Setup: venv, `pip install -r requirements.txt`, `.env`, `make_split`, `train`, `build_index`, the API, the web app. Get A1 to follow it on a fresh clone.
- [x] Evaluation: the command plus the metrics table from `eval/results/metrics.md`, with the split fingerprint
- [x] Escalation policy summary (link `docs/escalation-policy.md`)
- [x] Leakage controls (link `docs/data-and-leakage.md`)
- [x] Bonus features: cross-lingual, burst, PII
- [x] Limitations and next steps, and the team with their roles

### C.9 Demo script and rehearsal (by T+4:45)
- [x] Write `docs/demo-script.md`: a 5-minute run sheet with timings. Suggested flow:
  1. (0:30) The problem and what SentinelDesk does
  2. (1:00) German VPN outage (`demo-01`): ON_CALL badge, German draft, English precedents cited (cross-lingual)
  3. (0:45) Password reset (`demo-02`): Auto-Draft Ready, grounded draft with citations
  4. (0:45) Refund bait (`demo-03`) and injection (`demo-07`): the gate blocks fabrication and injection
  5. (0:45) Burst scenario: the major incident banner
  6. (0:45) Metrics strip, leakage controls, latency
  7. (0:30) Wrap-up
- [ ] Rehearse twice with the whole team. Record a backup screen capture of the full flow (in case the network fails).
