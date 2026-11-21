# EDA (KB only; test inputs used only for duplicate/length checks)

## Rows

KB=22869 (fit=20582, val=2287), test=5718

## Language mix (KB)

| language | n | % |
|---|---|---|
| en | 13055 | 57.1% |
| de | 9814 | 42.9% |

## Empty subject

KB: 13.6%, test inputs: 12.9%

## Class counts: type (KB)

| type | n | % |
|---|---|---|
| Incident | 9207 | 40.3% |
| Request | 6551 | 28.6% |
| Problem | 4796 | 21.0% |
| Change | 2315 | 10.1% |

## Class counts: priority (KB)

| priority | n | % |
|---|---|---|
| medium | 9202 | 40.2% |
| high | 8947 | 39.1% |
| low | 4720 | 20.6% |

## Class counts: queue (KB, top 10)

| queue | n | % |
|---|---|---|
| Technical Support | 6697 | 29.3% |
| Product Support | 4212 | 18.4% |
| Customer Service | 3411 | 14.9% |
| IT Support | 2741 | 12.0% |
| Billing and Payments | 2228 | 9.7% |
| Returns and Exchanges | 1166 | 5.1% |
| Service Outages and Maintenance | 907 | 4.0% |
| Sales and Pre-Sales | 726 | 3.2% |
| Human Resources | 463 | 2.0% |
| General Inquiry | 318 | 1.4% |

## Queue cardinality

10 queues in KB

## High-priority Incidents

KB total: 3936 (17.2%); fit: 3553; val: 383

## Text length (chars, build_text, KB)

p5=113 p25=261 p50=427 p75=589 p95=743 p99=845 max=1387

## Exact-duplicate bodies KB vs test

1 test bodies also appear in KB (0.02%)

## Placeholder tokens in KB body/answer

| token | n |
|---|---|
| `<tel_num>` | 8658 |
| `<name>` | 4924 |
| `<br>` | 2108 |
| `<acc_num>` | 2070 |
| `<email>` | 21 |
| `<website_url>` | 7 |
| `<amount>` | 6 |
| `<time>` | 4 |
| `<link>` | 3 |
| `<sn>` | 2 |
| `<organization>` | 1 |
| `<url>` | 1 |
| `<tool_name>` | 1 |
| `<platform_name>` | 1 |
| `<n_tel_num>` | 1 |

## A1.6: calibration and C sweep (KB val only, n=2,287)

Run with `python -m ml.calibrate`. ECE is top-label with 10 equal-width bins. Test metrics were never looked at.

| head | model | macro-F1 | ECE |
|---|---|---|---|
| type | LR C=1 | 0.8628 | 0.1319 |
| type | LR C=4 | 0.8796 | 0.0736 |
| type | **LR C=10** | **0.8838** | **0.0357** |
| type | LR C=4 + sigmoid cv=3 | 0.8672 | 0.0372 |
| queue | LR C=1 | 0.5271 | 0.2282 |
| queue | LR C=4 | 0.5762 | 0.1516 |
| queue | **LR C=10** | **0.6056** | **0.0951** |
| queue | LR C=4 + sigmoid cv=3 | 0.5331 | 0.0940 |
| priority | LR C=1 | 0.5710 | 0.0986 |
| priority | LR C=4 | 0.6132 | 0.0577 |
| priority | **LR C=10** | **0.6239** | **0.0117** |
| priority | LR C=4 + sigmoid cv=3 | 0.5583 | 0.0555 |

**Decision:** use C=10 for all heads (model version `tfidf-lr-v2-C10`). It has the best macro-F1 and the lowest ECE on every head. Sigmoid calibration lowers macro-F1 on every head, so it is rejected (the rule is to keep it only if macro-F1 does not drop). Queue ECE stays a little above 0.08 (0.095). The gate thresholds should treat queue confidence as only roughly calibrated.

After retraining: val macro-F1 type 0.8838, queue 0.6056, priority 0.6239. Val HPI recall (argmax) is 0.6580, up from 0.6501.
