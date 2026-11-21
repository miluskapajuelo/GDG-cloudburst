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
