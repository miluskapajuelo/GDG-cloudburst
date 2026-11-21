# SentinelDesk: UX and User Journey

## 0. The product in one sentence

**SentinelDesk helps a support team see instantly which tickets are critical and answer the rest with drafts in the customer's language. Every draft is based on real past resolutions, with its citation, and a human always has the final say.**

### The two problems we solve (and their UX side)

| Problem | How the user feels today | How they should feel with SentinelDesk |
|---|---|---|
| **Triage bottlenecks / missed incidents** | "I have 400 tickets and I don't know which one is taking a hospital down." Anxiety, fear of missing something. | "Critical items jump out at me. Nothing slips through." Control and calm. |
| **LLM hallucinations in auto-replies** | "I don't trust the bot: it invents integrations and refunds." Distrust and having to double-check everything. | "I can see where every sentence comes from. I can verify it in seconds." Verifiable trust. |

> **Core UX insight:** we are not selling *automation*, we are selling **trust + speed**. If the agent doesn't trust the AI, they will ignore it and the product is useless, no matter how good the model is.

---

## 1. Who are our users?

### Actor map

```
                ┌──────────────────────────┐
  Requester ───▶│   Ticket (subject+body)   │
 (customer EN/DE)└────────────┬─────────────┘
                             ▼
                    ┌─────────────────┐
                    │  SentinelDesk   │  ◀── Support Lead (supervises, measures)
                    └───┬─────────┬───┘
            safe to AI  │         │  escalate
                        ▼         ▼
               L1 Agent       L2 Engineer / On-call
            (reviews draft)   (handles the urgent case)
```

### Persona 1 (primary): **Lucía, L1 support agent**
- **Context:** handles 60–120 tickets per shift in English and German. Not a technical expert in everything.
- **Goal:** close tickets quickly and correctly, without making mistakes with the customer.
- **Frustrations:** manually searching for similar old tickets, translating and rewriting the same thing over and over, and the fear of promising something the company doesn't offer (e.g. SLA refunds).
- **What she needs from SentinelDesk:** a reliable draft, seeing *why* it says what it says, and editing and sending in a few clicks.
- **Quote:** *"If you give me an answer, tell me where you got it from."*

### Persona 2 (critical): **Markus, on-call / L2 engineer**
- **Context:** receives escalations. His time is expensive and interruptions are costly.
- **Goal:** learn about a real incident *within minutes* (e.g. the VPN outage affecting telemedicine) with full context.
- **Frustrations:** false alarms, escalations with no information, and finding out hours late.
- **What he needs:** a clear alert with the escalation reason, impact, related tickets and technical precedents.
- **Quote:** *"Escalate to me rarely, but escalate well and fast."*

### Persona 3: **Ana, Support Lead / Ops Manager**
- **Goal:** meet SLAs, balance workload, and prove the AI is safe.
- **Needs:** metrics (triage time, % escalated, % drafts accepted, edits) and traceability for audits.
- **Quote:** *"I need to be able to defend this tool to leadership and compliance."*

### Persona 4 (indirect): **The requester (end customer)**
- Doesn't use the tool, but **experiences its output**: the reply they receive.
- **Needs:** a reply in their language (EN/DE), professional in tone, correct, with no false promises, and fast.
- **UX risk:** a hallucinated reply damages the brand more than a slow one.

### Jobs To Be Done (JTBD)

| When... | I want to... | so that... |
|---|---|---|
| a new ticket arrives | instantly know its type, queue and priority | I don't waste time classifying |
| a ticket is critical | have it escalated automatically with context | the incident is fixed before it grows |
| a ticket is routine | get a grounded draft in the customer's language | I can reply in seconds without risk |
| I doubt the AI | see the evidence (past tickets) | I can decide with confidence |
| the AI gets it wrong | correct it easily | the system learns and doesn't repeat the mistake |

---

## 2. UX principles for SentinelDesk

1. **Human-in-the-loop by default.** The AI *proposes* and the human *decides*. In the MVP nothing is ever sent automatically.
2. **When in doubt, escalate (fail-safe).** High priority, low confidence or no precedent means escalate. A false-positive escalation is annoying; a false negative can cost lives (the hospital case).
3. **Visible, not hidden, explainability.** Every decision (classification, escalation or draft) shows its **"why"** in human language.
4. **Verifiable grounding.** Every claim in the draft must be traceable to a **historical ticket ID** that opens with one click.
5. **Calibrated, honest confidence.** Show confidence in an understandable way (High / Medium / Low + %), and don't hide uncertainty.
6. **Cognitive speed.** The important things come first (priority, decision) and details on demand (progressive disclosure).
7. **Native multilingual support.** The agent can read in their own language, but the reply goes out in the customer's language, and that is always visible.
8. **Human corrections are easy.** Reclassifying, de-escalating or editing has no friction, and the correction is recorded as feedback.

---

## 3. Main user journey: Lucía (L1 agent) handles a ticket

### Overview

```
1. Ticket      2. Automatic   3. Safety      4. Review       5. Review &     6. Send /      7. Feedback
   arrives ──▶   triage   ──▶   gate    ──▶   precedents ──▶  edit draft ──▶  close    ──▶   & learning
```

### Stage by stage

| Stage | Lucía's goal | What she does / sees | What she thinks / feels | Pain points to avoid | Opportunities / UX requirements |
|---|---|---|---|---|---|
| **1. Ticket arrives** | Know what's pending | Sorted inbox | 😐 "What's urgent?" | Flat list with no signals, overload | Sort by **priority and risk**, color + icon + text badges (not color alone), counter of "unassigned critical tickets" |
| **2. Automatic triage** | Understand the ticket without reading it all | `type`, `queue`, `priority` + confidence + detected language | 🙂 "Ah, it's billing, medium priority." | Unexplained labels and cryptic confidence | Clear chips, **confidence in bands** (High ≥ X, Medium, Low), **reclassify in 1 click** |
| **3. Safety gate** | Know whether she can use the AI or not | Status: ✅ *Safe for AI draft* or 🚨 *Human escalation* | 😌 or ⚠️ | Not knowing *why* it was escalated | **Explicit reason**: "High priority + outage keywords", "Confidence 41%", "No similar precedents", "Out of scope" |
| **4. Review precedents (RAG)** | Check there's a real basis | Top 3–5 past tickets with similarity, summary and resolution | 🤔 "Is it really similar?" | Irrelevant results or no context | Cards with **ID, title, % similarity, date and summarized resolution**, expandable. Mark a precedent as "not relevant" |
| **5. Review & edit draft** | Reply well and fast | Draft in EN/DE with citations `[#T-10432]` | 😊 "I can send this." or 🧐 "This doesn't add up." | Text with no sources, invented sentences, wrong language | **Clickable inline citations**, highlighting of which sentence comes from which ticket, warning when a sentence has *no* source, **translation view** for the agent, language selector |
| **6. Send / close** | Finish safely | Buttons: *Send*, *Edit*, *Escalate*, *Discard* | 😌 Accomplishment | Sending by accident | Light confirmation, a few seconds of *undo*, keyboard shortcuts |
| **7. Feedback** | (Implicit) improve the tool | 👍/👎, reason, captured edits | 😐 If it's effortful, she won't do it | Long forms | **1-click** feedback with preset reasons ("made something up", "tone", "language", "wrong precedent") |

### Emotional curve (target)

```
 Emotion
  😊 │                              ●───────●
     │                   ●─────────╯         ╲  ●
  😐 │  ●──────●────────╯                     ●╯
     │
  😟 │   (today: constant anxiety at stages 1, 4 and 5)
     └──────────────────────────────────────────────────▶
       Arrives Triage  Gate  Precedents  Draft  Send  Feedback
```

The **moments of truth** are the **Gate (3)** and the **draft (5)**: if they fail there, trust is lost.

---

## 4. Critical journey: incident escalation (Markus, on-call)

**Scenario:** *"VPN down: telemedicine and EMR integration unreachable since 08:10"*, in German, from a hospital.

| Stage | What happens | UX requirement |
|---|---|---|
| 1. Detection | The model classifies `Incident / Technical Support / high` | Must happen within seconds and land **at the very top** of the inbox |
| 2. Gate | Escalated automatically and **no customer reply is generated** | Clear message: "Escalated: high priority + impact on critical service" |
| 3. Notification | Markus receives the alert | Minimum content: **1-line summary, customer, impact, original language + translation, recent similar tickets (is there a mass outage?)** |
| 4. Context | Markus opens the ticket | Technical precedents (how it was solved before) *as internal reference*, not as a reply |
| 5. Action | Takes the ticket or reassigns it | **"Acknowledge"** button and a status visible to the whole team (avoids duplicated work) |
| 6. Closure | Resolves and documents it | The resolution goes into the precedent base, so the system improves |

**Extra opportunity (if time allows):** **cluster similar tickets** arriving within a few minutes ("12 VPN tickets in 10 min: possible outage") to move from reactive to proactive.

---

## 5. Requester journey (indirect)

```
Writes the ticket ─▶ (waits) ─▶ Receives a reply in their language ─▶ Solved? ─▶ Satisfied / reopens
```

Derived requirements:
- The reply is in **the same language** as the ticket (EN/DE) and in the appropriate formal register (in German, *Sie*).
- It must be **concise, professional and actionable**, with numbered steps where relevant.
- **Never** promise refunds, SLAs, integrations or troubleshooting steps that don't appear in the precedents.
- If escalated: a human acknowledgment ("Our technical team is already working on it") instead of a generated reply that might be wrong.

---

## 6. Information architecture and key screens

### Screen A: **Inbox / Triage queue**
- Columns: Priority · Subject · Type · Queue · Language · Confidence · Status (🚨 Escalated / ✍️ Draft ready / ✅ Sent) · Waiting time.
- Filters: priority, queue, language, status.
- Top banner: **"3 unassigned critical tickets"**.

### Screen B: **Ticket detail** (recommended 3-column layout)

```
┌───────────────────┬─────────────────────────────┬──────────────────────┐
│ ORIGINAL TICKET   │ AI DECISION                 │ PRECEDENTS (RAG)     │
│ Subject           │ Type: Incident    [edit]    │ #T-10432  92% ▸      │
│ Body (DE)         │ Queue: Tech Supp. [edit]    │ #T-09811  87% ▸      │
│ [Show translation]│ Priority: HIGH  ●●● Conf.High│ #T-07720  81% ▸      │
│                   │ ─────────────────────────── │                      │
│                   │ 🚨 ESCALATED                │                      │
│                   │ Reason: high priority +     │                      │
│                   │ critical service affected   │                      │
│                   │ ─────────────────────────── │                      │
│                   │ DRAFT (DE)     [EN ⇄ DE]    │                      │
│                   │ "...Neustart des Gateways   │                      │
│                   │  [#T-10432]..."             │                      │
│                   │ [Send] [Edit] [Escalate]    │                      │
└───────────────────┴─────────────────────────────┴──────────────────────┘
```

### Screen C: **Lead dashboard** (nice-to-have in 6 h)
- Tickets by priority and queue, % escalated, % of drafts sent without edits, average triage time and negative feedback by reason.

---

## 7. AI-specific UX patterns (trust and safety)

| Pattern | How to apply it |
|---|---|
| **Calibrated confidence** | Show it in bands + %, with a tooltip explaining what it means. Don't show 0.73 without context. |
| **Citations / grounding** | Every claim carries `[#ID]`. On hover, show the snippet from the historical ticket. |
| **Unsourced sentences** | If the model generates something not in the precedents, underline it as ⚠️ "unsupported" or, better, don't generate it. |
| **Honest refusal** | If there aren't enough precedents, show "No similar cases, human reply recommended" instead of a forced draft. |
| **Escalation reasons** | List of the rules that fired (transparent and auditable). |
| **Human control** | Reclassify, de-escalate (recording the reason) and edit the draft. Everything is logged. |
| **Loading states** | Step-by-step progress: "Classifying… → Searching precedents… → Drafting…". Reduces anxiety and explains latency. |
| **Non-anthropomorphic language** | Use "Suggested draft" instead of "The AI thinks…". |

---

## 8. Edge cases and states to design (don't forget!)

- [ ] **Low classification confidence**: escalate and show the reason.
- [ ] **No precedents** (or similarity below threshold): no draft, show an explanatory empty state.
- [ ] **Mixed language** (EN+DE) or misdetected: show the detected language and allow changing it.
- [ ] **Out-of-scope ticket** (spam, unsupported language, legal request): "Out of scope" status.
- [ ] **Very short** ("help!!!") or **very long** ticket.
- [ ] **Refund / SLA request**: always escalate or handle with care (risk of legal commitment).
- [ ] **LLM API failure / timeout**: graceful degradation. Classification stays pending and the ticket remains visible, never lost.
- [ ] **Empty inbox**: positive state ("All caught up").
- [ ] **Several agents on the same ticket**: "Lucía is viewing this" indicator.
- [ ] **Sensitive information / PII** in the ticket: consider masking it in the precedents view.

---

## 9. Accessibility and internationalization

- Priority and status **not by color alone**: also use icon and text (color blindness).
- WCAG AA contrast, full keyboard navigation and shortcuts (`E` escalate, `S` send, `J/K` navigate).
- UI ready for i18n (externalized strings); German text is ~30% longer, so design with room to spare.
- Dates and times in the agent's time zone, with the customer's local time visible when relevant.

---

## 10. Success metrics (UX + business + safety)

| Dimension | Metric |
|---|---|
| **Speed** | Time from arrival to triage; time to first response |
| **Safety** | **Recall of escalated `high` tickets** (target ≈ 100%); number of replies with unsourced claims |
| **Draft quality** | % sent without edits; average edit distance; 👍/👎 |
| **Trust** | % of times the agent opens citations (high at first, then dropping = trust earned) |
| **Classification** | Accuracy / F1 per `type`, `queue`, `priority`; confidence calibration |
| **Customer experience** | CSAT, reopen rate |

---

## 11. Step by step: building a user-centered product *from scratch*

### General process (Design Thinking + Lean)

1. **Empathize:** understand the users (interviews, observation, reviewing real tickets from the dataset).
2. **Define:** personas, JTBD, core problem and *How Might We* ("How might we make an agent trust a draft in under 10 seconds?").
3. **Ideate:** alternative flows, prioritized by impact versus effort.
4. **Prototype:** paper or Figma wireframes, then a minimal working prototype.
5. **Test:** tests with 3–5 users (even teammates playing the agent), watching where they hesitate.
6. **Iterate:** adjust and measure. Repeat.

### Applied to a 6-hour hackathon

| Time | Phase | UX deliverables | Suggested owner |
|---|---|---|---|
| **0:00–0:30** | Empathize & define | Read ~30 tickets from the dataset; validate personas and journey (this doc); pick **1 hero scenario** (hospital VPN) + **1 routine one** (password reset in DE) | Whole team |
| **0:30–1:00** | Ideate & wireframe | Wireframe the detail screen (section 6), define gate thresholds and the copy for escalation reasons | UX + PM |
| **1:00–4:00** | Build | Pipeline (classify → gate → RAG → draft) + UI with **states**: loading, escalated, draft, no precedents, error | Dev (backend + frontend) |
| **4:00–4:30** | Quick test | 2–3 people use the tool with no prior explanation. Note where they get lost | UX |
| **4:30–5:15** | Iterate | Fix the top 3 issues from the test; polish copy and citations | Whole team |
| **5:15–6:00** | Demo & story | Demo script (section 12), metrics and slides | PM |

### UX decision checklist before coding

- [ ] What is the **confidence threshold** for escalating? And the minimum **similarity** for generating a draft?
- [ ] Which rules force escalation? (`high` priority, outage keywords, refunds/SLA, no precedents, out of scope)
- [ ] How is confidence displayed? (bands + %)
- [ ] How are precedents cited in the draft? (`[#ID]` format)
- [ ] What does the agent see if the ticket is in German and they don't speak German? (side-by-side translation)
- [ ] What happens if the LLM fails?
- [ ] What actions can the human take? (reclassify, escalate, edit, send, feedback)
- [ ] What gets logged for auditing?

---

## 12. User-centered demo script (for judges)

1. **The pain (30 s):** "Lucía has 400 tickets. One of them is a hospital without VPN. Today it would take her hours to spot it."
2. **Critical ticket (60 s):** the German VPN ticket arrives. It appears at the top, 🚨 escalated with the reason explained. **No automatic reply is generated.** Markus gets the context.
3. **Routine ticket (60 s):** password reset in German. Classified, ✅ safe, 3 precedents, German draft with `[#T-xxxx]` citations. Click a citation to see the source. Send.
4. **Edge case (30 s):** an SLA refund request *without* precedents. The system **refuses to make things up** and escalates. *This is anti-hallucination in action.*
5. **Wrap-up (30 s):** metrics and why the agent trusts it: **transparency + human control**.

---

## 13. Hypotheses and open questions (to validate)

- H1: showing clickable citations increases the % of drafts sent without edits.
- H2: agents prefer confidence in bands over a numeric %.
- H3: explaining the escalation reason reduces manual de-escalations.
- Should the agent see the draft even on escalated tickets (as an internal reference)?
- Do agents need translation, or are they all bilingual?
- Who owns keeping the precedent base up to date?

---

*Living document: update it after every user test.*
