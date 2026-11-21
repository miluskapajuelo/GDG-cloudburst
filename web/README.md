# SentinelDesk UI

Agent workspace for SentinelDesk: Inbox, Ticket Detail, Analytics and Settings.
React + TypeScript + Vite + Tailwind v4 + Lucide.

```bash
cd ui
npm install
cp .env.example .env.local    # VITE_API_URL=http://localhost:8000
npm run dev                   # http://localhost:5173
```

The UI works without the backend. If the API is down, the header shows "Demo data" and "Test a ticket" uses a local fallback, with results labelled as mock.

## Screens

| Route | What it is for |
|---|---|
| `#/inbox` | Open tickets ordered by risk and grouped by safety decision: critical, needs review, ready to respond. Unacknowledged critical incidents and possible major incidents are pinned on top. |
| `#/inbox/:id` | Three-column workspace. Left: the customer's original message, translation and history. Centre: the safety decision with its reason, editable classification with confidence, and the response workspace. Right: the supporting historical resolutions. |
| `#/escalated`, `#/resolved` | The same list, scoped. |
| `#/analytics` | Escalation recall, response times, draft acceptance, confidence distribution and feedback reasons. |
| `#/settings` | Preferences and the safety-check thresholds (`GET /config`). |

Keyboard: `J`/`K` move, `Enter` open, `Esc` back, `/` or `⌘K` search, `⌘Enter` review and send.

## Trust rules built into the UI

- Nothing is sent without an approval dialog. It previews the exact text the customer receives (citation markers removed). Flagged tickets need an explicit confirmation.
- Critical incidents (`ON_CALL`) never get a suggested customer response. They show internal technical context for the engineer, and the agent may send only a human acknowledgement.
- Each statement in a suggested response is either cited (a clickable chip that opens the supporting ticket), a courtesy line, or highlighted as **"No reference"**. A citation to a ticket outside the retrieved history is shown in red.

## Data

- `src/data/mockBackend.ts`: every `triage` object is a `POST /triage` response in the exact shape of [docs/contract.md](../docs/contract.md).
- Seven inbox tickets are real rows from `data/aa_dataset-tickets-multi-lang-5-2-50-version.csv` (CSV rows 0–6). Three precedents are also real rows (rows 7, 8 and 10). All 10 fall in the **knowledge-base split** of `ml/make_split.py` (seed 42). Row 9 is a holdout test row and is deliberately excluded ([docs/data-and-leakage.md](../docs/data-and-leakage.md)).
- Everything else is hand-written demo data: the hospital VPN incident, the German password reset, red-team tickets and the other precedents.

## Contract gaps (the UI needs these; the API does not provide them yet)

Each needs the contract change process in CLAUDE.md rule 1:

1. **Translation** of non-English tickets and drafts (`Ticket.translation` in `src/types.ts`).
2. **Precedent resolution date** (currently looked up in mock data).
3. **`GET /analytics`** (shape: `AnalyticsSummary` in `src/types.ts`).
