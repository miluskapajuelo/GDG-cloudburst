# SentinelDesk: speaker notes

Presenter: Shaad. The slot is 5 minutes: 3 minutes of live demo, then 2 minutes of judge questions. The demo runs in the console. The deck in [slides.html](slides.html) shows only the evaluation, and you use it in the last minute of the demo. The slides name nobody. The credits are in this file.

## Who built what

Use this to credit the team and to hand questions to the right person.

| Part | Built by | Shown in |
|---|---|---|
| Data split, leakage checks, classifier, calibration, API service | Shaad Qureshi (A1) | Slides 3 and 5, demo predictions panel |
| Holdout evaluation, LLM-sample grounding eval, threshold sweep, red-team runner | Gustavo Buitrago (A2) | Slides 1, 2, 4 and 6 |
| Retrieval and FAISS index, cross-lingual matching, language detection, PII masking, burst detector | Karan Patel (B1) | Demo: English precedents for a German ticket, burst banner |
| Escalation gate and reason codes, prompt, Gemini drafting, citation check, injection patterns | Prithvi Poojari (B2) | Demo: reasons panel, citations, injection block. Slides 4 and 8 |
| Operator console, approval flow, README, demo run sheet | Miluska Pajuelo (C) | The whole demo |

## Set up (10 minutes before)

1. Pull `main` and restart the API: `uvicorn api.main:app --port 8000`. In the console, open **Thresholds** and check that `T_SIM` is 0.5.
2. Check that the top bar says **Live**, **Demo data** is off and the metrics strip shows numbers. Triage one warm-up ticket, then reload to clear the inbox.
3. Pre-run the burst to save demo time. Go to **Inbox** > **Run burst scenario** > **Run burst scenario**, wait for all 4 rows, then close the dialog. The red banner stays at the top of the inbox. Do this less than 15 minutes before your slot, so that demo-01 joins the same burst.
4. Optional: add `VITE_AGENT_NAME=Shaad Qureshi` to `web/.env.local` and restart the console, so the sidebar shows your name.
5. Tab 1: the console at `http://localhost:5173`, on the inbox. Tab 2: `docs/presentation/slides.html`, on slide 1, in full screen (F). Ctrl+Tab moves between them.

## The 3 minutes

| Clock | What | Where |
|---|---|---|
| 0:00 to 0:10 | What SentinelDesk does | Console inbox |
| 0:10 to 0:55 | demo-01, German hospital VPN outage | Console |
| 0:55 to 1:25 | demo-13, safe ticket with an AI draft and approval | Console |
| 1:25 to 1:45 | demo-07, prompt injection | Console |
| 1:45 to 2:05 | Burst banner (pre-run) | Console inbox |
| 2:05 to 2:30 | Slide 1, holdout summary | Slides |
| 2:30 to 2:50 | Slide 2, high-priority incidents | Slides |
| 2:50 to 3:00 | Slide 5, leakage, and the close | Slides |

Slides 3, 4, 6, 7 and 8 are for questions only. If you run late, drop demo-07 and say the slide 5 line in one sentence.

Every live ticket comes from **Test a ticket** (top right) > **Presets** > pick the preset > **Triage**. The "Live run" lines come from two runs against the live API on 21 November 2026. Gemini output changes from run to run.

### 0:00 to 0:10, the opening

> "SentinelDesk triages IT support tickets in English and German. A safety gate sends urgent tickets to a person. For the rest, the AI drafts replies only from past resolutions, and a person approves them."

### 0:10 to 0:55, demo-01 (German hospital VPN outage)

Preset: **DE: hospital VPN outage (headline demo)**.

- Expect **Escalate to On-Call Engineer**.
- Live run: `HIGH_PRIORITY_INCIDENT` with P(high) 0.75 and P(Incident) 0.49, plus `LOW_CLASSIFIER_CONFIDENCE` (type 0.49 < 0.50). The top precedents are English VPN tickets, TKT-17145 (0.81) and TKT-18467 (0.80), tagged **Cross-lingual** and **Cited**. Because you pre-ran the burst, the decision card also shows similar reports in the last 15 minutes.
- Point at the reasons, then at the English precedents. Click one citation chip in the internal draft.

> "The gate reads probabilities, not only the top label. The model isn't sure if this is an Incident or a Problem, but 49% Incident is above our 30% line, so it goes to on-call. The customer wrote in German, and the best evidence is in English. We find it anyway, because both languages share one embedding space. For an outage, the AI draft is only internal context for the engineer."

Credit (optional, 3 seconds): "Karan built the cross-lingual retrieval, and Prithvi built the gate."

### 0:55 to 1:25, demo-13 (remote access not working)

Preset: **BURST 4/4 EN: remote access not working**.

- Expect **Auto-Draft Ready** with no risk reasons. Live run: Auto-Draft both times, with 2 or 3 citations.
- Click **Review and send**. The dialog shows the exact customer text with the citations removed. Tick the box and send.

> "A safe ticket gets a draft where every statement cites a past ticket. Even then, a person looks, ticks and sends."

### 1:25 to 1:45, demo-07 (prompt injection)

Preset: **EN: prompt injection + refund demand**.

- Live run: on-call with `PROMPT_INJECTION_SUSPECTED`, `UNSUPPORTED_REQUEST` and `HIGH_PRIORITY_INCIDENT`. There is no draft, and the triage took about 30 ms because Gemini was never called.

> "'Ignore all previous instructions' is caught before any LLM call. The gate also blocks the refund demand, because no past resolution grants it."

### 1:45 to 2:05, burst banner

Click **Inbox**. Point at the red banner: "Possible major incident: 4 similar tickets in 15 minutes".

> "One at a time, these look like routine VPN tickets. Several in a few minutes from different customers means one major incident, so we flag them together."

Switch to the slides (Ctrl+Tab).

### 2:05 to 2:30, slide 1 (holdout summary)

> "Now the evaluation. This is a 20% holdout of 5,718 tickets that no model, index or threshold ever saw. The number we care about most: 91% of true high-priority incidents get escalated, against 69% for the classifier alone. Type macro-F1 is 0.88. In a 40-ticket sample with Gemini on, all 39 drafts passed the citation check."

### 2:30 to 2:50, slide 2 (high-priority incidents)

> "Of the 995 real high-priority incidents, 880 go straight to on-call and 22 to human review. The price is that 47% of all tickets go to a person. We chose that, because a missed outage costs more than a review."

### 2:50 to 3:00, slide 5 (leakage) and the close

> "We fixed and fingerprinted the split, and only the scorer reads the test labels, after the predictions exist. Thank you. We're happy to take questions."

## If something goes wrong

| What you see | What to say or do |
|---|---|
| `LLM_UNAVAILABLE` | "Gemini didn't answer in time, so the gate sent it to a person instead of guessing. That's the designed behaviour." Carry on. |
| `LLM_INSUFFICIENT_EVIDENCE` on demo-13 | "Gemini judged the evidence too thin and wrote a holding reply, so a person takes it." Skip the approval step. |
| A draft takes 10 seconds or more | Gemini is rate limiting. The API retries after 2, 4 and 8 seconds. Talk about the reasons panel while it waits. |
| Top bar says "API offline" | Switch on **Demo data** and open SD-24871 (hospital VPN). Say that it is sample data, then go to the slides early. |
| No burst banner in the inbox | Skip the burst step and say: "A burst needs 3 similar tickets in 15 minutes." |

## Questions (2 minutes)

Hand each question to the person who built that part (see the table at the top). If they are not there, use the answer below. Slides 3 to 8 support these answers.

**Why is 47% escalation acceptable?** (Gustavo, slide 2) It is a deliberate trade. On validation, the untuned gate escalated 34% of tickets and caught 80% of high-priority incidents. The tuned gate escalates 48% and catches 90%. The thresholds live in `agent/config.py`, so a support team can move that line.

**Why TF-IDF and logistic regression?** (Shaad, slide 3) It trains in seconds and gives calibrated probabilities that the gate can threshold. Validation ECE is 0.012 for priority and 0.036 for type. Type macro-F1 is already 0.88.

**Why is priority F1 only 0.63?** (Shaad, slide 3) Priority labels are noisy, and the text often leaves out the business context. Recall on high priority is 0.687 by top label. The gate does not depend on the top label because it uses probabilities.

**Where does the classifier go wrong?** (Shaad, slide 3) Mostly Incident against Problem: 344 incidents predicted as problems and 364 problems predicted as incidents.

**How do you know the drafts don't invent facts?** (Prithvi, slide 4) Gemini must return the cited IDs. The check rejects any ticket ID that retrieval did not return, and money or percentage figures that the cited answers do not contain. In the sample, 39 of 39 drafts passed. Other claims still rely on the person who approves.

**How did you test the gate?** (Gustavo and Prithvi, slide 4) 15 hand-written demo and red-team tickets: prompt injection, refund bait, an out-of-scope ticket, personal data and a burst. All 15 take the expected route with Gemini on and off.

**How do you prevent leakage?** (Shaad, slide 5) We fixed the split (seed 42, fingerprint `5a2ede85f9fb`). We never write the holdout answers to disk. Only `eval/run_eval.py` reads the test labels, after it saves all predictions. Thresholds come from a validation slice of the knowledge base. Only 1 test body (0.02%) is an exact copy of a knowledge-base body.

**How fast is it?** (Gustavo, slide 6) The median is 40 ms without the LLM and about 1.1 seconds with the Gemini draft. The p95 with the LLM is about 15 seconds because of retries after rate limits.

**What do the numbers not show?** (Gustavo, slide 7) The cost of a false escalation for a real team. Language detection matches the dataset label on 88.3% of tickets, but about 29% of rows labelled German are English text. The grounding sample has 40 tickets.

**Does cross-lingual retrieval work?** (Karan) In a 5-topic check, 13 of 25 results for German queries were English tickets, on topic in 4 of the 5 topics. German retrieval is still weaker than English.

**How does the burst detector avoid false alarms?** (Karan, slide 8) It needs 3 or more tickets in 15 minutes with cosine ≥ 0.65 and a shared rare term. A rare term appears in fewer than 2% of past tickets, such as "vpn". With 10 random tickets in the window, false banners were 0%. Cosine alone gave 21%.

**What personal data reaches Gemini?** (Karan) None of the masked types. IBANs, emails, card numbers, IP addresses, phone numbers and account numbers become placeholders first.

## The slides

| Slide | Content | Use |
|---|---|---|
| 1 | Holdout summary: 0.907, 0.878, 39 / 39, 40 ms | Spoken |
| 2 | High-priority incidents: where the 995 went, and the escalation cost | Spoken |
| 3 | Classifier: F1 and accuracy per label, error pattern, calibration | Questions |
| 4 | Grounded drafts: the 40-ticket sample, red-team 15 / 15 | Questions |
| 5 | Leakage controls | Spoken (one line) |
| 6 | Time per stage | Questions |
| 7 | Backup: what the numbers do not show | Questions |
| 8 | Backup: thresholds and reason codes | Questions |

Keys: arrows, Page Up and Page Down, or a clicker. Home and End jump to the first and last slide. T switches to the light theme.

## Numbers in one place

All from `eval/results/metrics.md` (generated 2026-11-21 19:51 UTC, split `5a2ede85f9fb`, `T_SIM` 0.50).

- Holdout: 5,718 tickets. Knowledge base: 22,869 tickets.
- Macro-F1: type 0.878, queue 0.594, priority 0.630.
- High-priority incidents (995): escalation recall 0.907 (880 on-call, 22 review, 93 AI draft). Classifier alone 0.692.
- All tickets: 47% escalated (1,984 on-call, 695 review, 3,039 AI draft).
- Latency without the LLM: p50 40 ms, p95 60 ms. With the LLM: p50 1,116 ms, p95 14,697 ms.
- Grounding (40 tickets): citation check 39 of 39, reply language 39 of 39, holding reply 2 of 40, Gemini unavailable 1 of 40.
- Thresholds: P(high) ≥ 0.20 and P(Incident) ≥ 0.30 for on-call. Confidence below 0.50 (type, priority) or 0.25 (queue) for review. Similarity below 0.50 means no precedent. Burst: cosine ≥ 0.65 plus a shared rare term, 3 or more tickets in 15 minutes.
