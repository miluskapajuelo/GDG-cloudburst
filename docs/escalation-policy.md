# Escalation and Safety Gate Policy

**Owner:** B2 (`prithvipoojari`): `agent/gate.py`, `agent/config.py`
**Tuning support:** A2 runs `eval/tune_thresholds.py`. B1 supplies similarity distributions.

The gate decides whether a ticket gets `AUTO_DRAFT` (the AI draft may be sent after a quick human glance) or `ESCALATE` (a human must handle it). Every decision must be **explainable**: each escalation carries one or more reason codes with a plain-language message that includes the numbers behind it.

## 1. Rules

The gate runs in two phases.

### Phase 1: `pre_draft_gate(predictions, precedents, text)`

Evaluate every rule; do not stop at the first match. Collect all reasons.

| # | Code | Fires when | Route | Draft allowed? |
|---|---|---|---|---|
| 1 | `PROMPT_INJECTION_SUSPECTED` | `text` matches an injection pattern (§3) | HUMAN_REVIEW | **No** |
| 2 | `HIGH_PRIORITY_INCIDENT` | `P(priority=high) ≥ T_HIGH_PRIORITY_P` **and** `P(type=Incident) ≥ T_INCIDENT_P` | **ON_CALL** | Yes (a reference draft for the engineer) |
| 3 | `LOW_CLASSIFIER_CONFIDENCE` | `conf(type) < T_CONF_TYPE` or `conf(priority) < T_CONF_PRIORITY` or `conf(queue) < T_CONF_QUEUE` | HUMAN_REVIEW | Yes |
| 4 | `NO_PRECEDENT` | no precedents, or `precedents[0].similarity < T_SIM` | HUMAN_REVIEW | **No** (nothing to ground on) |
| 5 | `UNSUPPORTED_REQUEST` | the ticket asks for a sensitive action category (§2), and **no** top-k precedent answer contains a term from the same category | HUMAN_REVIEW | Yes (the LLM must write a holding reply) |

Rule 2 uses **probabilities, not argmax labels**. This lets us trade a little precision for much higher recall on high-priority incidents, which is the metric the brief singles out. The message must show both probabilities.

### Phase 2: `finalize_escalation(pre, draft, citation_problems, llm_error)`

| # | Code | Fires when | Route |
|---|---|---|---|
| 6 | `LLM_INSUFFICIENT_EVIDENCE` | `draft.status == "INSUFFICIENT_EVIDENCE"` | HUMAN_REVIEW |
| 7 | `CITATION_CHECK_FAILED` | `validate_citations` returned problems (the message lists them) | HUMAN_REVIEW |
| 8 | `LLM_UNAVAILABLE` | API error, timeout, safety block or empty response. The draft is `null`. | HUMAN_REVIEW |

When `skip_llm=true`, Phase 2 adds nothing.

### Final decision

```
status = "ESCALATE" if reasons else "AUTO_DRAFT"
route  = "ON_CALL" if any(r.code == "HIGH_PRIORITY_INCIDENT") else ("HUMAN_REVIEW" if reasons else None)
badge  = {"ON_CALL": "Escalate to On-Call Engineer",
          "HUMAN_REVIEW": "Human Review Required",
          None: "Auto-Draft Ready"}[route]
draft.for_human_review = (status == "ESCALATE")
```
Order of `reasons`: ON_CALL reasons first, then in rule-number order.

## 2. Sensitive-request lexicon (rule 5)

Matching is case-insensitive substring matching on the masked ticket text and on each precedent's `answer`. Keep the lexicon in `agent/config.py` as `SENSITIVE_LEXICON: dict[str, list[str]]`. The values below are a starting point. Tune them on KB val so that rule 5 alone fires on less than about 10% of val tickets.

| Category | English | German |
|---|---|---|
| `REFUND_COMPENSATION` | refund, reimburse, compensation, money back, chargeback, credit note | rückerstattung, erstatten, entschädigung, geld zurück, gutschrift |
| `PRICING_DISCOUNT` | price, pricing, quote, discount, license fee, cost per | preis, rabatt, lizenzgebühr, kostenvoranschlag |
| `LEGAL_CONTRACT` | lawsuit, legal action, liability, lawyer, terminate contract, gdpr, delete all my data | klage, rechtliche schritte, haftung, anwalt, vertrag kündigen, dsgvo, datenlöschung |
| `SLA_GUARANTEE` | sla, guarantee, uptime commitment, service credit, penalty | garantie, verfügbarkeitszusage, vertragsstrafe |
| `SECURITY_OVERRIDE` | disable mfa, bypass, share password, give me admin, root access | mfa deaktivieren, passwort mitteilen, adminrechte geben, umgehen |

The message format is: `Ticket requests REFUND_COMPENSATION ("refund"); no retrieved precedent resolves this.`

## 3. Prompt-injection patterns (rule 1)

Use case-insensitive regexes in `agent/config.py` as `INJECTION_PATTERNS`:

```
ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)
disregard (all |any |the )?(previous|prior|above) (instructions|rules)
(reveal|print|show) (your|the) (system )?prompt
you are now|act as (an? )?(admin|system|developer)|developer mode|jailbreak
</?(system|ticket|precedents?|instructions?)>
ignorier(e|en)? (alle |die )?(vorherigen|obigen|bisherigen) (anweisungen|regeln)
vergiss (alle |deine )?(anweisungen|regeln)
```

Rule 1 is a cheap first filter. The draft prompt is the second defence, because it treats ticket text as data (see B2's task file).

## 4. Thresholds (`agent/config.py`)

| Name | Default | Meaning |
|---|---|---|
| `T_HIGH_PRIORITY_P` | 0.20 | min P(priority=high) for rule 2 |
| `T_INCIDENT_P` | 0.30 | min P(type=Incident) for rule 2 |
| `T_CONF_TYPE` | 0.50 | min top-class prob for type |
| `T_CONF_PRIORITY` | 0.50 | min top-class prob for priority |
| `T_CONF_QUEUE` | 0.25 | min top-class prob for queue (many classes, so the floor is lower) |
| `T_SIM` | 0.50 | min top-1 cosine similarity |
| `TOP_K` | 5 | precedents retrieved |
| `BURST_SIM` | 0.65 | cosine to count two incoming tickets as the same failure |
| `BURST_MIN` | 3 | tickets in the window to raise the banner |
| `BURST_WINDOW_MIN` | 15 | window length, in minutes |

Every threshold can be overridden by an env var of the same name, prefixed `SENTINEL_` (for example `SENTINEL_T_SIM=0.6`).

## 5. Tuning procedure (T+3:30, on KB val only)

1. A2 runs `python -m eval.tune_thresholds`. For each val ticket it runs: `classifier.predict`, then `retriever.search(..., exclude_ids={ticket_id})`, then `pre_draft_gate`. It sweeps the thresholds and writes `eval/results/threshold_sweep.md`.
2. Targets, in priority order:
   1. **HPI escalation recall ≥ 0.90.** This is the fraction of true high-priority Incidents that get `ESCALATE`.
   2. Overall escalation rate between **30% and 50%**. If everything escalates, the gate has no value.
   3. `NO_PRECEDENT` on val below 10%. In-domain tickets should find precedents. Start from the 5th percentile of val top-1 similarity.
3. Sanity check: the out-of-scope demo ticket (`demo-08`) must fall below `T_SIM`.
4. B2 updates the defaults in `agent/config.py`. Log the decision in `docs/plan.md`, for example: `T+3:40 — T_SIM 0.55→0.58 (val p5) — prithvipoojari`.
