# Gate threshold sweep (KB validation rows only)

- Generated: 2026-11-21T18:14:27Z
- Val tickets: 2287
- True high-priority Incidents in val: 383
- Settings evaluated: 5488
- Pre-draft rules only (as with skip_llm). Retrieval excludes each ticket's own KB row.
- Threshold-free rules: PROMPT_INJECTION_SUSPECTED on 0 tickets, UNSUPPORTED_REQUEST on 25 (0.0109).
- Targets (escalation-policy section 5): HPI escalation recall >= 0.90, escalation rate 0.30-0.50, NO_PRECEDENT < 0.10.

## Recommended row

Selection: all three targets met. Within the feasible set the highest HPI escalation recall wins, then the lowest escalation rate, then the fewest changes from the current defaults.

| Threshold | Current default | Recommended |
|---|---|---|
| T_HIGH_PRIORITY_P | 0.3500 | 0.2000 |
| T_INCIDENT_P | 0.4000 | 0.2500 |
| T_CONF_TYPE | 0.4500 | 0.4500 |
| T_CONF_PRIORITY | 0.4500 | 0.4500 |
| T_CONF_QUEUE | 0.2500 | 0.3000 |
| T_SIM | 0.5500 | 0.8510 |

| Metric | Current defaults | Recommended |
|---|---|---|
| hpi_escalation_recall | 0.7990 | 0.9243 |
| escalation_rate | 0.3376 | 0.4967 |
| no_precedent_rate | 0.0000 | 0.0988 |
| hpi_on_call_recall | 0.7598 | 0.8695 |
| on_call_rate | 0.2589 | 0.3603 |
| low_conf_rate | 0.0914 | 0.1242 |

For `agent/config.py` (B2, prithvipoojari):

```python
T_HIGH_PRIORITY_P = 0.2
T_INCIDENT_P = 0.25
T_CONF_TYPE = 0.45
T_CONF_PRIORITY = 0.45
T_CONF_QUEUE = 0.3
T_SIM = 0.851
```

## Sanity check: out-of-scope ticket demo-08

Top-1 similarity 0.2410 vs recommended T_SIM 0.851: **PASS** (must be below, so it escalates with NO_PRECEDENT).

## Val top-1 similarity distribution

| p1 | p2 | p5 | p10 | p25 | p50 |
|---|---|---|---|---|---|
| 0.7689 | 0.7890 | 0.8250 | 0.8510 | 0.8965 | 0.9390 |

## One threshold at a time (others at the recommended row)

### T_HIGH_PRIORITY_P

| T_HIGH_PRIORITY_P | HPI esc recall | Esc rate | NO_PRECEDENT | ON_CALL rate |
|---|---|---|---|---|
| 0.2000 | 0.9243 | 0.4967 | 0.0988 | 0.3603 |
| 0.2500 | 0.9034 | 0.4735 | 0.0988 | 0.3319 |
| 0.3000 | 0.8825 | 0.4609 | 0.0988 | 0.3113 |
| 0.3500 | 0.8642 | 0.4438 | 0.0988 | 0.2882 |
| 0.4000 | 0.8538 | 0.4268 | 0.0988 | 0.2589 |
| 0.4500 | 0.8303 | 0.4145 | 0.0988 | 0.2326 |
| 0.5000 | 0.7963 | 0.3944 | 0.0988 | 0.2081 |

### T_INCIDENT_P

| T_INCIDENT_P | HPI esc recall | Esc rate | NO_PRECEDENT | ON_CALL rate |
|---|---|---|---|---|
| 0.2500 | 0.9243 | 0.4967 | 0.0988 | 0.3603 |
| 0.3000 | 0.9217 | 0.4867 | 0.0988 | 0.3498 |
| 0.3500 | 0.9164 | 0.4797 | 0.0988 | 0.3384 |
| 0.4000 | 0.9112 | 0.4683 | 0.0988 | 0.3240 |
| 0.4500 | 0.8982 | 0.4582 | 0.0988 | 0.3078 |
| 0.5000 | 0.8747 | 0.4447 | 0.0988 | 0.2908 |
| 0.5500 | 0.8590 | 0.4338 | 0.0988 | 0.2763 |

### T_CONF_TYPE = T_CONF_PRIORITY

| T_CONF_TYPE | HPI esc recall | Esc rate | NO_PRECEDENT | ON_CALL rate |
|---|---|---|---|---|
| 0.3500 | 0.9138 | 0.4561 | 0.0988 | 0.3603 |
| 0.4000 | 0.9138 | 0.4687 | 0.0988 | 0.3603 |
| 0.4500 | 0.9243 | 0.4967 | 0.0988 | 0.3603 |
| 0.5000 | 0.9295 | 0.5505 | 0.0988 | 0.3603 |

### T_CONF_QUEUE

| T_CONF_QUEUE | HPI esc recall | Esc rate | NO_PRECEDENT | ON_CALL rate |
|---|---|---|---|---|
| 0.1500 | 0.9164 | 0.4652 | 0.0988 | 0.3603 |
| 0.2000 | 0.9191 | 0.4670 | 0.0988 | 0.3603 |
| 0.2500 | 0.9191 | 0.4718 | 0.0988 | 0.3603 |
| 0.3000 | 0.9243 | 0.4967 | 0.0988 | 0.3603 |

### T_SIM

| T_SIM | HPI esc recall | Esc rate | NO_PRECEDENT | ON_CALL rate |
|---|---|---|---|---|
| 0.4500 | 0.8956 | 0.4495 | 0.0000 | 0.3603 |
| 0.5000 | 0.8956 | 0.4495 | 0.0000 | 0.3603 |
| 0.5500 | 0.8956 | 0.4495 | 0.0000 | 0.3603 |
| 0.6000 | 0.8956 | 0.4499 | 0.0004 | 0.3603 |
| 0.7890 | 0.8982 | 0.4613 | 0.0197 | 0.3603 |
| 0.8250 | 0.9034 | 0.4757 | 0.0490 | 0.3603 |
| 0.8510 | 0.9243 | 0.4967 | 0.0988 | 0.3603 |

## Settings meeting all three targets: 68 (highest HPI recall first, top 15)

| T_HIGH_PRIORITY_P | T_INCIDENT_P | T_CONF_TYPE | T_CONF_PRIORITY | T_CONF_QUEUE | T_SIM | HPI esc recall | Esc rate | NO_PRECEDENT |
|---|---|---|---|---|---|---|---|---|
| 0.2000 | 0.2500 | 0.4500 | 0.4500 | 0.3000 | 0.8510 | 0.9243 | 0.4967 | 0.0988 |
| 0.2000 | 0.3000 | 0.4500 | 0.4500 | 0.3000 | 0.8510 | 0.9217 | 0.4867 | 0.0988 |
| 0.2000 | 0.2500 | 0.4500 | 0.4500 | 0.2000 | 0.8510 | 0.9191 | 0.4670 | 0.0988 |
| 0.2000 | 0.2500 | 0.4500 | 0.4500 | 0.2500 | 0.8510 | 0.9191 | 0.4718 | 0.0988 |
| 0.2000 | 0.3000 | 0.4500 | 0.4500 | 0.2000 | 0.8510 | 0.9164 | 0.4569 | 0.0988 |
| 0.2000 | 0.3000 | 0.4500 | 0.4500 | 0.2500 | 0.8510 | 0.9164 | 0.4617 | 0.0988 |
| 0.2000 | 0.2500 | 0.4500 | 0.4500 | 0.1500 | 0.8510 | 0.9164 | 0.4652 | 0.0988 |
| 0.2000 | 0.3500 | 0.4500 | 0.4500 | 0.3000 | 0.8510 | 0.9164 | 0.4797 | 0.0988 |
| 0.2000 | 0.3000 | 0.4500 | 0.4500 | 0.1500 | 0.8510 | 0.9138 | 0.4552 | 0.0988 |
| 0.2000 | 0.2500 | 0.3500 | 0.3500 | 0.3000 | 0.8510 | 0.9138 | 0.4561 | 0.0988 |
| 0.2000 | 0.2500 | 0.4000 | 0.4000 | 0.3000 | 0.8510 | 0.9138 | 0.4687 | 0.0988 |
| 0.2000 | 0.3000 | 0.3500 | 0.3500 | 0.3000 | 0.8510 | 0.9112 | 0.4460 | 0.0988 |
| 0.2000 | 0.3500 | 0.4500 | 0.4500 | 0.2500 | 0.8510 | 0.9112 | 0.4543 | 0.0988 |
| 0.2000 | 0.3000 | 0.4000 | 0.4000 | 0.3000 | 0.8510 | 0.9112 | 0.4587 | 0.0988 |
| 0.2000 | 0.4000 | 0.4500 | 0.4500 | 0.3000 | 0.8510 | 0.9112 | 0.4683 | 0.0988 |

