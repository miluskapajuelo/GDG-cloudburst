# SentinelDesk holdout metrics

- Generated: 2026-11-21T19:09:10Z
- Split fingerprint: `5a2ede85f9fb`
- Test tickets scored: 5718
- Triage errors: 0 (counted as wrong predictions and as not escalated)
- Mode: `api.service.triage(subject, body, skip_llm=True)`, in-process, one ticket at a time
- LLM sample: 40 tickets with skip_llm=False (section below)

## Classifier

| Head | Macro-F1 | Weighted-F1 | Accuracy |
|---|---|---|---|
| type | 0.8781 | 0.8694 | 0.8697 |
| queue | 0.5936 | 0.6047 | 0.6055 |
| priority | 0.6304 | 0.6416 | 0.6418 |

## High-priority incidents (true priority=high and type=Incident)

| Support | Classifier recall (pred high and Incident) | Escalation recall (status ESCALATE) |
|---|---|---|
| 995 | 0.6915 | 0.9065 |

Outcome of the true high-priority incidents:

| Outcome | Count |
|---|---|
| ESCALATE / ON_CALL | 880 |
| AUTO_DRAFT | 93 |
| ESCALATE / HUMAN_REVIEW | 22 |

## Escalation

Escalation rate: 0.4687

| Outcome | Count |
|---|---|
| AUTO_DRAFT | 3038 |
| ESCALATE / ON_CALL | 1984 |
| ESCALATE / HUMAN_REVIEW | 696 |

Reason codes (every reason of every ticket is counted):

| Reason code | Count | Share of tickets |
|---|---|---|
| PROMPT_INJECTION_SUSPECTED | 0 | 0.0000 |
| HIGH_PRIORITY_INCIDENT | 1984 | 0.3470 |
| LOW_CLASSIFIER_CONFIDENCE | 1078 | 0.1885 |
| NO_PRECEDENT | 1 | 0.0002 |
| UNSUPPORTED_REQUEST | 57 | 0.0100 |

## Language detection

Accuracy against the `language` label: 0.8827

Caveat: the `language` label is noisy. B1 found that about 29% of KB rows labelled `de` are English text (agent/NOTES.md), so disagreement on `de` rows is mostly label noise, not detector error.

| Label | Rows | Accuracy | Detected as |
|---|---|---|---|
| de | 2435 | 0.7244 | de: 1764, en: 668, es: 2, fr: 1 |
| en | 3283 | 1.0000 | en: 3283 |

## Latency (ms, skip_llm)

Rows timed: 5718

| Stage | p50 | p95 |
|---|---|---|
| pii | 0 | 0 |
| language | 1 | 2 |
| classify | 5 | 8 |
| retrieve | 28 | 43 |
| gate | 1 | 1 |
| generate | 0 | 0 |
| eval_wall | 38 | 55 |
| **total** | 38 | 55 |

`eval_wall` is the wall time of the `triage()` call measured by the eval script.

## LLM sample (grounding, skip_llm=False)

Run 3 of at most 3. Sampled 40 test inputs, stratified on the skip_llm predictions (never on labels): 10 predicted high/Incident, 20 with German reply language. Errors: 0. LLM calls made: 40.
Drafts are in `eval/results/llm_samples.jsonl` (model outputs only: no labels, no test answers).

| Metric | Value | Count | Denominator |
|---|---|---|---|
| Citation validity (no CITATION_CHECK_FAILED) | 1.0000 | 22 | 22 drafts returned |
| OK drafts with at least 1 citation | 1.0000 | 21 | 21 OK drafts |
| INSUFFICIENT_EVIDENCE rate | 0.0250 | 1 | 40 sampled tickets |
| LLM_UNAVAILABLE rate | 0.4500 | 18 | 40 sampled tickets |
| Reply-language match | 1.0000 | 22 | 22 drafts with text |

Latency with the LLM (ms):

| Measure | p50 | p95 | n |
|---|---|---|---|
| total (all sampled tickets) | 940 | 1416 | 40 |
| generate (tickets with an LLM call) | 906 | 1391 | 40 |

Reason codes in the sample:

| Reason code | Count |
|---|---|
| HIGH_PRIORITY_INCIDENT | 15 |
| LLM_INSUFFICIENT_EVIDENCE | 1 |
| LLM_UNAVAILABLE | 18 |
| LOW_CLASSIFIER_CONFIDENCE | 9 |

## Thresholds (from `api.service.get_config()`)

| Name | Value |
|---|---|
| T_HIGH_PRIORITY_P | 0.2 |
| T_INCIDENT_P | 0.3 |
| T_CONF_TYPE | 0.5 |
| T_CONF_PRIORITY | 0.5 |
| T_CONF_QUEUE | 0.25 |
| T_SIM | 0.55 |
| TOP_K | 5 |
| BURST_SIM | 0.65 |
| BURST_MIN | 3 |
| BURST_WINDOW_MIN | 15 |

## Per-class report: type

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Change | 0.9768 | 0.9720 | 0.9744 | 607 |
| Incident | 0.8371 | 0.8442 | 0.8406 | 2259 |
| Problem | 0.7111 | 0.6982 | 0.7046 | 1216 |
| Request | 0.9909 | 0.9945 | 0.9927 | 1636 |

Confusion matrix: type (rows = true, columns = predicted)

| true \ pred | Change | Incident | Problem | Request |
|---|---|---|---|---|
| Change | 590 | 6 | 1 | 10 |
| Incident | 4 | 1907 | 344 | 4 |
| Problem | 2 | 364 | 849 | 1 |
| Request | 8 | 1 | 0 | 1627 |

## Per-class report: queue

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Billing and Payments | 0.8302 | 0.7857 | 0.8073 | 560 |
| Customer Service | 0.5132 | 0.5438 | 0.5280 | 857 |
| General Inquiry | 0.6667 | 0.3908 | 0.4928 | 87 |
| Human Resources | 0.7538 | 0.4336 | 0.5506 | 113 |
| IT Support | 0.5248 | 0.4899 | 0.5067 | 692 |
| Product Support | 0.5570 | 0.5683 | 0.5626 | 1040 |
| Returns and Exchanges | 0.5880 | 0.5055 | 0.5437 | 271 |
| Sales and Pre-Sales | 0.5864 | 0.4948 | 0.5367 | 192 |
| Service Outages and Maintenance | 0.8113 | 0.7137 | 0.7594 | 241 |
| Technical Support | 0.6157 | 0.6841 | 0.6481 | 1665 |

Confusion matrix: queue (rows = true, columns = predicted)

| true \ pred | Billing and Payments | Customer Service | General Inquiry | Human Resources | IT Support | Product Support | Returns and Exchanges | Sales and Pre-Sales | Service Outages and Maintenance | Technical Support |
|---|---|---|---|---|---|---|---|---|---|---|
| Billing and Payments | 440 | 43 | 1 | 1 | 10 | 23 | 9 | 2 | 1 | 30 |
| Customer Service | 25 | 466 | 3 | 7 | 59 | 103 | 19 | 19 | 4 | 152 |
| General Inquiry | 1 | 14 | 34 | 0 | 7 | 10 | 2 | 4 | 0 | 15 |
| Human Resources | 1 | 13 | 0 | 49 | 5 | 16 | 5 | 2 | 1 | 21 |
| IT Support | 10 | 66 | 2 | 5 | 339 | 54 | 11 | 8 | 5 | 192 |
| Product Support | 16 | 106 | 2 | 1 | 63 | 591 | 22 | 15 | 7 | 217 |
| Returns and Exchanges | 3 | 35 | 4 | 1 | 8 | 40 | 137 | 6 | 0 | 37 |
| Sales and Pre-Sales | 11 | 24 | 1 | 0 | 5 | 22 | 10 | 95 | 3 | 21 |
| Service Outages and Maintenance | 1 | 14 | 0 | 0 | 14 | 11 | 3 | 0 | 172 | 26 |
| Technical Support | 22 | 127 | 4 | 1 | 136 | 191 | 15 | 11 | 19 | 1139 |

## Per-class report: priority

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| high | 0.6734 | 0.6867 | 0.6800 | 2231 |
| low | 0.5725 | 0.5681 | 0.5703 | 1174 |
| medium | 0.6457 | 0.6360 | 0.6408 | 2313 |

Confusion matrix: priority (rows = true, columns = predicted)

| true \ pred | high | low | medium |
|---|---|---|---|
| high | 1532 | 204 | 495 |
| low | 195 | 667 | 312 |
| medium | 548 | 294 | 1471 |

