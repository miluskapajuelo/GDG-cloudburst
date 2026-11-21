# SentinelDesk: speaker notes

Presenter: Shaad. The slot is 5 minutes, then 3 minutes of judge questions. These notes follow the 15 slides in [slides.html](slides.html). The demo part follows the run sheet in [docs/demo-script.md](../demo-script.md), cut down to fit around the slides.

## Set up (10 minutes before)

1. Pull `main`, then restart the API so it runs the current code: `uvicorn api.main:app --port 8000`. The API that ran on this laptop from 13:58 still used `T_SIM` 0.55 and had no Gemini retry. After the restart, open **Thresholds** in the console and check that `T_SIM` is 0.5.
2. Optional: add `VITE_AGENT_NAME=Shaad Qureshi` to `web/.env.local` and restart the console. The sidebar then shows your name. Without it, the sidebar shows "Support Agent".
3. Do the rest of the checklist in the run sheet. Check that the top bar says **Live**, **Demo data** is off and the metrics strip shows numbers. Triage one warm-up ticket, reload to clear the inbox, then click **Reset burst**.
4. Open `docs/presentation/slides.html` in the browser in tab 1. Open the console at `http://localhost:5173` in tab 2. Ctrl+Tab moves between them.
5. In the slides, press F for full screen. Arrow keys, Page Up and Page Down, or a clicker move between slides. T switches to the light theme if the projector washes out the dark one.

## Timing

| Slide | Content | Time | Clock at end |
|---|---|---|---|
| 1 | Title | 0:10 | 0:10 |
| 2 | The problem | 0:20 | 0:30 |
| 3 | What happens to one ticket | 0:20 | 0:50 |
| 4 to 8 | Team, 10 seconds each | 0:50 | 1:40 |
| 9 | Live demo (switch to the console) | 2:20 | 4:00 |
| 10 | Results | 0:30 | 4:30 |
| 11 | Leakage controls | 0:20 | 4:50 |
| 12 | Limitations and next steps, then the closing line | 0:10 | 5:00 |
| 13 to 15 | Backup, for questions only | | |

If you run late, cut slide 12 down to the closing line and drop demo-07 from the demo. Say one sentence for slide 11.

## Slide by slide

### 1. Title (0:10)

> "Hi, I'm Shaad. This is SentinelDesk, and the five of us built it today. It triages IT support tickets in English and German. Urgent tickets go to a person. The AI drafts replies only from past resolutions, and a person approves every one."

### 2. The problem (0:20)

> "Support desks fail in two ways. A hospital VPN outage lands in the same inbox as feature questions, and escalation takes hours. And AI chatbots invent answers, like refunds or integrations that don't exist. The brief asked us to fix both at once."

### 3. What happens to one ticket (0:20)

Point along the row of steps from left to right.

> "One ticket goes through six steps. We mask personal data, detect the language, and predict type, queue and priority. Then we find the five most similar past tickets, in either language. The gate picks a route: on-call engineer, human review, or an AI draft that a person approves. Each step has an owner, so here's the team."

### 4. Shaad (0:10)

> "I did the data split and the classifier. It's TF-IDF with logistic regression, calibrated so the gate can trust its probabilities. Type macro-F1 on the holdout is 0.88."

### 5. Karan (0:10)

> "Karan built retrieval: one multilingual index over 22,869 past tickets, so a German ticket finds English answers. He also built the PII masking and the burst detector. That's the red banner at the bottom."

### 6. Prithvi (0:10)

> "Prithvi built the gate and the drafting. Every escalation carries a reason code with its numbers. A citation check rejects any ticket ID or money figure the evidence doesn't support."

### 7. Gustavo (0:10)

> "Gustavo tuned the gate thresholds on validation data, never on the test set. With his thresholds, the gate escalates 91% of high-priority incidents. The classifier alone catches 69%. He also wrote the grounding evaluation and the red-team runner."

### 8. Miluska (0:10)

> "Miluska built the console you'll see now. Every citation links to its source, and nothing goes to a customer until a person approves it."

### 9. Live demo (2:20)

Switch to the console tab (Ctrl+Tab). Every ticket comes from **Test a ticket** (top right) > **Presets** > pick the preset > **Triage**. The screenshot on the slide is the fallback if the network fails.

The "Live run" lines below come from two runs against the live API on 21 November 2026 (14:51 and 14:53). Gemini output changes from run to run, so expect small differences.

**a. demo-01, German hospital VPN outage (0:50).** Preset: **DE: hospital VPN outage (headline demo)**.

- Expect **Escalate to On-Call Engineer**.
- Live run: `HIGH_PRIORITY_INCIDENT` with P(high) 0.75 and P(Incident) 0.49, plus `LOW_CLASSIFIER_CONFIDENCE` (type 0.49 < 0.50). The top two precedents are English VPN tickets, TKT-17145 (0.81) and TKT-18467 (0.80). The console tags both as **Cross-lingual** and **Cited**.
- Point at the reason, then at the English precedents, then click one citation chip in the internal draft.

> "The gate reads probabilities, not only the top label. The model isn't sure if this is an Incident or a Problem, but 49% Incident is above our 30% line, so it goes to on-call. The customer wrote in German, and the best evidence is in English. We find it anyway, because both languages share one embedding space. The AI draft here is internal context for the engineer. The customer only gets a short acknowledgement from a person."

Translate the German line aloud: "Since 07:40, none of our hospital sites can connect over VPN."

**b. demo-13, remote access not working (0:30).** Preset: **BURST 4/4 EN: remote access not working**.

- Expect **Auto-Draft Ready** with no risk reasons. Live run: Auto-Draft both times, with 2 or 3 citations (TKT-18467, TKT-17145, TKT-21818).
- Click **Review and send**. The dialog shows the exact customer text with the citations removed. Tick the box, send, and point at the **Undo** toast.

> "Even the safe path has a person in the loop. One look, one tick, then it goes."

**c. demo-03 and demo-07, refund bait and prompt injection (0:30).**

Preset: **EN: double charge + refund/compensation bait**.

- Expect **Escalate to On-Call Engineer**. The run sheet used to say Human Review, but the tuned thresholds send it to on-call.
- Live run: `HIGH_PRIORITY_INCIDENT` (P(high) 0.48, P(Incident) 0.39), `LOW_CLASSIFIER_CONFIDENCE`, `UNSUPPORTED_REQUEST` and `LLM_INSUFFICIENT_EVIDENCE`. The `UNSUPPORTED_REQUEST` message names the SLA request (`"sla"`).

> "The customer wants a refund plus compensation for an SLA breach. No past resolution grants that compensation, so the AI may not promise it. A person decides."

Preset: **EN: prompt injection + refund demand**.

- Live run: on-call with `PROMPT_INJECTION_SUSPECTED`, `UNSUPPORTED_REQUEST` and `HIGH_PRIORITY_INCIDENT`. There is no draft, and the whole triage took about 30 ms because Gemini was never called.

> "'Ignore all previous instructions' is caught before any LLM call, so nothing gets drafted."

**d. Burst scenario (0:30).** Go to **Inbox** > **Run burst scenario** > **Run burst scenario** in the dialog.

- Live run: rows 1 and 2 show no burst. Row 3 turns on the burst with 3 tickets, label "VPN / client". Row 4 makes it 4 tickets, label "VPN".

> "One at a time, these look like routine VPN tickets. Three or more in a few minutes from different customers point to one major incident, so we flag them as one."

Close the dialog. The red banner stays at the top of the inbox. Switch back to the slides (Ctrl+Tab) and go to slide 10.

**If something goes wrong in the demo**

| What you see | What to say or do |
|---|---|
| `LLM_UNAVAILABLE` | "Gemini didn't answer in time, so the gate sent it to a person instead of guessing. That's the designed behaviour." Carry on. |
| `LLM_INSUFFICIENT_EVIDENCE` on a ticket you expected as Auto-Draft | "Gemini judged the evidence too thin and wrote a holding reply, so a person takes it." This happened once on demo-02 in our runs. |
| A draft takes 10 seconds or more | Gemini is rate limiting us. The API retries after 2, 4 and 8 seconds. Keep talking about the reasons panel while it waits. |
| Top bar says "API offline" | Switch on **Demo data**, open SD-24871 (hospital VPN), and tell the same story. Or go back to the slides and use the screenshot. |
| No burst banner by row 4 | Click **Reset burst**, then **Run again**. If it still does not appear, say the rule needs 3 similar tickets in 15 minutes, and move on. |

### 10. Results (0:30)

> "These numbers come from a 20% holdout of 5,718 tickets that we never trained or tuned on. Type macro-F1 is 0.88. The number we care about most: 91% of true high-priority incidents get escalated, against 69% for the classifier alone. The cost is that 47% of all tickets go to a person. We chose that, because a missed outage costs more than a review. In a 40-ticket sample with Gemini on, all 39 drafts passed the citation check."

### 11. Leakage controls (0:20)

> "On leakage: we fixed the split with seed 42, and every laptop checked the same fingerprint. Only the scorer reads the test labels, after the predictions exist. We tuned thresholds on a validation slice of the training data, never on the test set."

### 12. Limitations and next steps, and the close (0:10)

> "Queue and priority are still modest, and German retrieval is weaker than English. Next, we'd try a fine-tuned multilingual encoder and hybrid retrieval for German."

If you are late, skip the line above and say only the closing line:

> "That's SentinelDesk. Each of us can take questions on our own part. Thank you."

## Questions: who answers and what to say

Hand each question to the person who built that part. If they are not in the room, use the answer below. The backup slides are at the end of the deck: press End for slide 15, then the left arrow for 14 and 13.

| Topic | Who |
|---|---|
| Split, leakage, classifier, calibration, API service | Shaad |
| Holdout metrics, threshold sweep, red-team runner | Gustavo |
| Retrieval, cross-lingual, language detection, PII, burst | Karan |
| Gate, reason codes, prompt, citation check, injection | Prithvi |
| Console, approval flow, README | Miluska |

**Why TF-IDF and logistic regression, and not a transformer?** It trains in seconds and gives calibrated probabilities that the gate can threshold. At C=10 the validation ECE is 0.012 for priority and 0.036 for type. Type macro-F1 is already 0.88. A fine-tune would have cost hours for an uncertain gain.

**Why is priority F1 only 0.63?** Priority labels are noisy. Similar wording is high in one ticket and medium in another, and the text often leaves out the business context. The gate does not need a perfect top label because it uses probabilities.

**Isn't 47% escalation too much?** It is a deliberate trade. On validation, the untuned gate escalated 34% of tickets and caught 80% of high-priority incidents. The tuned gate escalates 48% and catches 90%. The thresholds live in `agent/config.py`, so a support team can move that line.

**Why did demo-01 show only 49% Incident?** The classifier splits the type between Incident (0.49) and Problem (0.49). The gate needs P(Incident) ≥ 0.30 together with P(high) ≥ 0.20, so it escalates anyway. That is the reason to gate on probabilities.

**How do you know the drafts don't invent things?** Gemini must return JSON with the cited IDs. The validator rejects any ticket ID that was not retrieved, and it flags money or percentage figures that the cited answers do not contain. A person approves every reply. In the 40-ticket sample, 39 of 39 drafts passed the citation check. The figure check covers money and percentages only, so other claims still rely on the reviewer.

**How do you handle prompt injection?** Seven English and German patterns catch override attempts before any LLM call, and they block drafting. The prompt also treats the ticket and the precedents as quoted data.

**What happens when Gemini is down or rate limited?** The API retries after 2, 4 and 8 seconds on HTTP 429 or 5xx. If the call still fails, the ticket gets `LLM_UNAVAILABLE` and goes to human review with its triage and precedents. In the latest 40-ticket sample, 1 ticket fell back that way. The retries push the p95 time with the LLM to about 15 seconds.

**Does cross-lingual retrieval really work?** In a 5-topic check, 13 of 25 results for German queries were English tickets, and they were on topic in 4 of the 5 topics. German retrieval is still weaker than English.

**How does burst detection avoid false alarms?** It needs at least 3 tickets in 15 minutes with cosine ≥ 0.65 and a shared rare term. A rare term appears in fewer than 2% of past tickets, such as "vpn". With 10, 20 and 30 random tickets in the window, false banners were 0%, 3.3% and 11%. Cosine alone gave 21% with 10 tickets.

**What personal data reaches Gemini?** None of the masked types. IBANs, emails, card numbers (Luhn-checked), IP addresses, phone numbers and account numbers become placeholders first. Ticket IDs, dates and version numbers stay as they are.

**How do you prevent leakage?** We fixed the split (seed 42, fingerprint `5a2ede85f9fb`). We never write the holdout answers to disk. Only `eval/run_eval.py` reads the test labels, after it saves all predictions. The index build asserts that the index holds no test ticket. Only 1 test body (0.02%) is an exact copy of a knowledge-base body.

**How fast is it?** The median is 40 ms per ticket without the LLM and about 1.1 seconds with the Gemini draft. Retrieval is the slowest local step at 29 ms.

## Numbers in one place

All from `eval/results/metrics.md` (generated 2026-11-21 19:51 UTC, split `5a2ede85f9fb`, `T_SIM` 0.50).

- Holdout: 5,718 tickets. Knowledge base: 22,869 tickets.
- Macro-F1: type 0.878, queue 0.594, priority 0.630.
- High-priority incidents (995): escalation recall 0.907 (902). Classifier alone 0.692. Escalation rate 47%.
- Latency without the LLM: p50 40 ms, p95 60 ms. With the LLM: p50 1,116 ms, p95 14,697 ms.
- Grounding (40 tickets): citation validity 39 of 39, reply language 39 of 39, `INSUFFICIENT_EVIDENCE` 2 of 40, `LLM_UNAVAILABLE` 1 of 40.
- Thresholds: P(high) ≥ 0.20 and P(Incident) ≥ 0.30 for on-call. Confidence below 0.50 (type, priority) or 0.25 (queue) for review. Similarity below 0.50 means no precedent. Burst: cosine ≥ 0.65 plus a shared rare term, 3 or more tickets in 15 minutes.
