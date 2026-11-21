# SentinelDesk demo script (5 minutes)

**Presenter:** drives the console and speaks. **Second person:** watches the clock, holds up the time cards, and answers numbers questions from the crib sheet at the bottom.
Screen: 1280×720 projector, browser zoom 100%, dark theme (Settings → Appearance). Only the console tab is open.

## Before the judges arrive (T-10 min)

- [ ] API running with real models (not `SENTINEL_MOCK`): `uvicorn api.main:app --port 8000`.
- [ ] Console open at `http://localhost:5173`. The top bar says **Live**, not "API offline". **Demo data** is switched off.
- [ ] **Thresholds** button opens values that say "Live values from GET /config".
- [ ] Inbox shows the **Holdout metrics** strip with numbers (not "Eval not run yet").
- [ ] Warm-up: run demo-02 once through **Test a ticket** so models and the Gemini client are loaded. Then reload the page to clear the inbox.
- [ ] Open **Run burst scenario** → **Reset burst**, then close the dialog. The burst detector starts empty.
- [ ] Backup screen capture is on this laptop's desktop, ready to play.
- [ ] Phone timer set to 5:00.

## Run sheet

All tickets come from **Test a ticket** (top right) → **Presets**. Pick the preset, then press **Triage**. The console opens the ticket.

### 0:00–0:30 · The problem and what SentinelDesk does (30 s)

> "Support teams get thousands of tickets in English and German. The dangerous ones, like an outage at a hospital, get buried, and AI reply bots make things up. SentinelDesk reads each ticket, classifies it, finds how we solved similar tickets before in either language, and then a safety gate decides: on-call engineer, human review, or an AI draft. The AI draft is grounded in cited past tickets and is never sent without a person approving it."

Screen: the empty Inbox with the Holdout metrics strip visible. Don't explain the strip yet.

### 0:30–1:30 · German VPN outage, demo-01 (60 s)

Preset: **DE: hospital VPN outage (headline demo)** → **Triage**.

Point at, in this order:
1. Header badge **Escalated to on-call** and the decision card **Escalate to On-Call Engineer**.
2. **Why this decision:** `HIGH_PRIORITY_INCIDENT` with the probabilities, P(high) and P(Incident).
   > "The gate uses probabilities, not just the top label. A likely-urgent incident goes to a human even when the model isn't sure. A missed outage costs more than a review."
3. Right column **Supporting history:** English VPN tickets tagged **Cross-lingual** and **Cited**.
   > "The customer wrote in German. The best evidence is in English, and we find it anyway: one multilingual embedding space."
4. Centre, **Technical context for the engineer** (marked "Internal, not sent"): the AI draft is in German and cites those English tickets. Click one citation chip: the matching ticket on the right highlights.
   > "Every sentence points to a past resolution. Click it and you see the source."
5. The customer-facing part is only a short **Customer acknowledgement** written by a human. The AI does not answer an outage.

Don't click the translation toggle: live tickets have no translation. Translate the German line aloud: "Since 07:40 none of our hospital sites can connect over VPN."

### 1:30–2:15 · Password reset, demo-02 (45 s)

Preset: **EN: password reset email not arriving** → **Triage**.

1. Decision card: **Auto-Draft Ready**, no risk reasons.
2. **Suggested response:** citation chips after statements. The stats line says every statement is referenced, or highlights any statement with **No reference**.
3. **Review and send** → the approval dialog shows exactly what the customer receives, with citations removed. **Approve and send** stays disabled until the confirmation box is ticked.
   > "Even the safe path has a human in the loop. One glance, one tick, then it goes."

Tick, send, and point at the 5-second **Undo** toast. Don't wait for it to finish.

### 2:15–3:00 · Refund bait and prompt injection, demo-03 and demo-07 (45 s)

Preset: **EN: double charge + refund/compensation bait** → **Triage**.
- Decision: **Human Review Required** with `UNSUPPORTED_REQUEST` (refund or compensation that no past resolution supports).
  > "The customer demands 20% compensation. None of our past resolutions grant that, so the AI is not allowed to promise it. A human decides."

Preset: **EN: prompt injection + refund demand** → **Triage**.
- Reasons include `PROMPT_INJECTION_SUSPECTED`. It may also route to on-call because the text claims an outage.
  > "'Ignore all previous instructions…' is caught by the gate before any LLM call, and drafting is blocked."

### 3:00–3:45 · Burst scenario (45 s)

Go to **Inbox** → **Run burst scenario** → in the dialog, **Run burst scenario**.

- Four VPN tickets arrive one second apart, in English and German. Rows 1–2 say "No burst yet". From row 3 the red banner appears: **Possible major incident: N similar tickets in 15 minutes**, with the label.
  > "Individually these look like routine VPN tickets. Together, three in a few minutes from different customers, they're a major incident. We flag it so the team treats them as one."
- Close the dialog: the same red banner is pinned at the top of the Inbox.

### 3:45–4:30 · Metrics, leakage controls, latency (45 s)

Point at the **Holdout metrics** strip in the Inbox.
> "These are on a 20% holdout of 5,718 tickets the system never trained or tuned on. Type macro-F1 is 0.88. The number we care about most: 91% of true high-priority incidents are escalated, against 69% for the classifier alone."

> "Leakage: the split is fixed with seed 42, and every machine checked the same fingerprint. Test labels live in a separate file that only the scoring step opens, after predictions exist. Thresholds were tuned on a validation slice of the training data, never on the test set."

Click **Thresholds** in the top bar: "If you want our exact thresholds, they're one click away, live from the API."

Open any triaged ticket and point at **End-to-end latency**: "Triage without the draft takes about 40 ms. With the Gemini draft, the median is under a second."

### 4:30–5:00 · Wrap-up (30 s)

> "SentinelDesk finds the dangerous tickets, answers the safe ones from evidence, refuses to make things up, and works across English and German. Every decision shows its reasons, and a person always approves what's sent. Thank you, happy to take questions."

## If something goes wrong

| Problem | Do this |
|---|---|
| Draft shows `LLM_UNAVAILABLE` | Say: "Gemini didn't answer in time, so the gate escalated to a human instead of guessing. That's the designed behaviour." Carry on. Classification and precedents are still shown. |
| API down, top bar says "API offline" | Switch on **Demo data** in the top bar. The yellow banner explains it's sample data. Open SD-24871 (hospital VPN) and SD-24874 (password reset) from the Inbox and continue the same story. |
| Network down completely | Play the backup screen capture and narrate over it. |
| Burst banner doesn't appear by row 4 | Click **Reset burst**, then **Run again**. If it still doesn't fire, say the detector needs three similar tickets within 15 minutes, and move on. |
| Running over time | Skip demo-07 and the Thresholds click. |

## Crib sheet for questions

All numbers come from `eval/results/metrics.md` (split `5a2ede85f9fb`) and the team notes.

- **Macro-F1:** type 0.878, queue 0.594, priority 0.630.
- **High-priority incidents (n = 995):** escalation recall 0.907 (902). Classifier alone: 0.692. Overall escalation rate: 47%.
- **Thresholds:** P(high) ≥ 0.20 and P(Incident) ≥ 0.30 → on-call. Confidence below 0.50 (type, priority) or 0.25 (queue) → review. Similarity below 0.55 → no precedent. Burst: cosine ≥ 0.65 plus a shared rare term, at least 3 tickets within 15 minutes.
- **Latency:** p50 38 ms without the LLM, 940 ms with it (40-ticket sample).
- **Grounding:** 22 of 22 returned drafts passed the citation check, and 22 of 22 were in the requested language. Gemini was unavailable for 18 of 40.
- **Why TF-IDF + logistic regression?** It trains in seconds and gives calibrated probabilities that the gate can threshold. Type macro-F1 is already 0.88.
- **Why is priority F1 modest?** The labels are noisy and depend on business context the text doesn't state. That's why the gate uses probabilities.
- **PII:** IBANs, emails, cards (Luhn-checked), IPs, phone and account numbers are masked before any text reaches Gemini.
- **Leakage:** fixed split (seed 42), one shared fingerprint, test answers never written to disk, test labels read only by the scorer. Only 1 test body (0.02%) duplicates a training body.

Details: [README.md](../README.md), [docs/escalation-policy.md](escalation-policy.md), [docs/data-and-leakage.md](data-and-leakage.md).

## Rehearsal log

| Run | Date and time | Who | Total time | What broke / what to change |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |

Backup recording: file name and location: ______________________
