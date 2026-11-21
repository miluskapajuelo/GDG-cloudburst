# Agent notes (Team B)

B1 writes only under `## B1`, B2 only under `## B2`.

## B1

Owner: `Karanpatel3114`. Modules: `lang.py`, `pii.py`, `build_index.py`, `retrieve.py`, `burst.py`. Tests: `tests/test_b1_*.py`.

### Measured numbers (M1 laptop, KB split = 22,869 tickets)
- `python -m agent.build_index`: **97 s** end to end (90 s embedding on MPS). On CPU-only machines expect a few minutes.
- `Retriever.embed` takes ~20 ms on CPU, and `search` (k=5, exact `IndexFlatIP`) takes ~1 ms.
- `detect_language` takes < 1 ms per ticket after warm-up.

### Integration gotcha: macOS segfault (torch + faiss)
On macOS, PyTorch and faiss-cpu each bundle an OpenMP runtime. If `faiss` is imported before `torch`, or runs multi-threaded, CPU encoding segfaults (exit 139). `agent/retrieve.py` and `agent/build_index.py` import `sentence_transformers` first and call `faiss.omp_set_num_threads(1)`. **Don't reorder those imports, and don't `import faiss` anywhere else.** Tested with scikit-learn loaded first (the API's import order): works.

### Data findings
- **The dataset already masks PII with its own placeholders.** Counts in the KB: `<tel_num>` 8.7k, `<name>` 4.9k, `[Name]` 2.1k, `<acc_num>` 2.1k, plus variants (`[Telefonnummer]`, `{name}`, `[Kontonummer]`, …). Raw emails, IPs and IBANs are essentially absent. `mask_pii` leaves those placeholders unchanged (they contain no digits). → **B2:** the prompt's rule 6 should also name `<name>`, `<tel_num>`, `<acc_num>`, `[Name]` so the LLM keeps them as they are.
- **The `language` label is noisy.** On a 3,000-ticket KB sample, 364 of 1,272 rows labelled `de` (29%) are actually English text. In 98.9% of those disagreements, the detector and a function-word count agree. No `en` row was misdetected. So raw agreement with the label is **~88%**, and that gap is label noise, not detector error. → **A2:** report language accuracy with this caveat (or score only on rows where the text contains German function words).
- **Queue labels are clean** in the recommended file: exactly 10 queues, 4 types, 3 priorities.

### Language detection (`lang.py`)
Lingua, restricted to en/de/fr/es/pt/it. Placeholder tokens are removed before detection so `[PHONE]` can't flip a short German ticket to English. When lingua's top call is en or de with confidence < 0.90, a function-word vote breaks the tie. This fixes German tickets full of English tech words ("Der Outlook Client crasht beim Login…"). No regressions on the KB sample.

### PII masking (`pii.py`)
Order: IBAN → EMAIL → CARD (Luhn-checked, so long phone numbers aren't eaten) → IP (v4 + simple v6) → PHONE (intl `+49`/`0049`, national `0…` with ≥7 digits, NA formats) → ACCOUNT (keyword + ≥5 digits; only the number is replaced). Verified not masked: `TKT-01234`, dates `21.11.2026`, ISO timestamps, versions `2.4.1`, `0x80070005`, the dataset's own placeholders. demo-09 gives EMAIL 1, PHONE 1, ACCOUNT 1, IP 1.

### Burst detection (`burst.py`): proposed `BURST_SIM` change, 0.75 → 0.65
- At the planned cosine-only **0.75, demo-12 does not activate** (EN↔DE VPN tickets score 0.69–0.73, so the banner only appears at demo-13).
- Lowering the cosine threshold alone causes false alarms. The dataset is templated, so random KB pairs already have p99 cosine 0.74. With 10 random tickets in a 15-min window: 0.75 → 4% false banners, 0.65 → 21%.
- **Rule now used:** cosine ≥ `BURST_SIM` **and** at least one shared *rare* term (a term in < 2% of KB tickets: "vpn" 0.28%, "timeout" 0.18%, vs "system" 17%, "issue" 26%). `build_index` writes the common-term list to `artifacts/kb_common_terms.json` (439 terms).

  | Rule | False banner (10 / 20 / 30 random tickets in window) | demo-12 active? |
  |---|---|---|
  | cosine ≥ 0.75 only (current default) | 4% / – / 51% | no |
  | cosine ≥ 0.65 + rare term (proposed) | **0% / 3.3% / 11%** | **yes** |

  → **B2:** please set `BURST_SIM = 0.65` in `agent/config.py` (and the escalation-policy table, once the team agrees).
- `BurstDetector` has one optional, backward-compatible kwarg, `common_terms=None`. By default it loads the JSON from `$SENTINEL_ARTIFACTS_DIR`. The constructor call in the contract is unchanged.
- The label comes from the rare terms most of the cluster shares, e.g. "VPN" or "VPN / client".
- Inactive bursts return the contract's inactive object exactly (`cluster_size: 1`, `label: null`, `request_ids: []`).

### Retrieval quality notes (feeds B1.5 / B2)
- en VPN query: top 3 are all VPN tickets (0.70–0.73). en billing "charged twice": top 3 are all double-charge tickets (0.78–0.80).
- Demo tickets (masked full text, top hits):
  - **demo-01 (de VPN outage): 0.81 / 0.80, both English VPN tickets.** This is the best cross-lingual showcase.
  - demo-02 (en password reset): 0.63–0.65, English login-problem tickets.
  - **demo-08 (out of scope): top-1 0.24**, far below `T_SIM` 0.55 → `NO_PRECEDENT`, as expected (input for B1.7).
  - **demo-15 (de printer): top-1 0.53, an English "Printer Not Printing" ticket**, so cross-lingual works. But it's **just below `T_SIM` 0.55**, so it gets `NO_PRECEDENT`, and the rest of the top 5 is off-topic (~0.46). The KB has only ~6–7 printer tickets ("drucker" 0.026%, "printer" 0.031%). → **B2:** don't rely on demo-15 as the cross-lingual showcase; use demo-01.
- TODO B1.5: full 5+5 cross-lingual table.

## B2

### Prompt and gate changes

The prompt escapes XML delimiters in the incoming ticket and in historical evidence. It asks Gemini to ground each substantive claim in a cited resolution, describe possible causes conditionally, and refer security changes and destructive actions to a specialist. Drafts avoid saying someone already performed work on the current ticket.

The injection filter also handles variable whitespace, formal German imperatives, and reserved tags with attributes. The sensitive-request terms retain the documented defaults pending calibration. When the gate finds a sensitive request that no precedent answer supports, the ticket still escalates with `UNSUPPORTED_REQUEST`, and Gemini writes the reply. This replaces an earlier fixed template, because the assignment asks for a tailored response that refuses to fabricate. The prompt tells Gemini to promise nothing and to return `INSUFFICIENT_EVIDENCE` with a holding reply that acknowledges the issue, says a specialist will follow up and asks for missing details. The citation and figure check still runs on that reply, and a human reviews it before it is sent.

Sensitive terms now match from the start of a word in both tickets and precedent answers, so compounds such as `Rückerstattungsantrag` still count. `SLA`, `SLAs`, and `umgehen` require whole words. This avoids false matches in `bislang`, `Slack`, `translate`, and `umgehend`.

B2.6 normalizes dataset placeholders to `[name]`, `[tel_num]`, and `[acc_num]` and converts HTML line breaks before escaping ticket and precedent text. The prompt names both sets of placeholders. The final reply decodes HTML entities before citation extraction and validation.

The prompt targets 80 to 100 words for a grounded reply, excluding citations. B2.6 removes the length rewrite so each successful draft uses one Gemini generation request. `.env.example` shows the `SENTINEL_REPLY_MIN_WORDS` and `SENTINEL_REPLY_MAX_WORDS` overrides.

The demo-07 fixture expects `ON_CALL` when the incident thresholds fire. Prompt injection still blocks drafting. The gate reports all unsupported sensitive categories in a single `UNSUPPORTED_REQUEST` reason.

### Judge Q&A

- **Grounding.** Gemini returns a structured draft. The pipeline checks bracketed ticket IDs against the retrieved cases and compares currency amounts and percentages with the answers shown to Gemini. It flags drafts that fail validation for human review.
- **Prompt injection.** The gate blocks drafting when it detects common English or German override attempts. The prompt treats both tickets and precedent excerpts as quoted data, with escaped field delimiters.
- **Escalation reasons.** `HIGH_PRIORITY_INCIDENT` takes the on-call route when both model probabilities reach their thresholds. `LOW_CLASSIFIER_CONFIDENCE` flags a prediction head below its floor. `NO_PRECEDENT` means retrieval was empty or its top result was below the similarity floor. `PROMPT_INJECTION_SUSPECTED` flags an instruction override. `UNSUPPORTED_REQUEST` flags a sensitive action category missing from the retrieved answers. `LLM_INSUFFICIENT_EVIDENCE` records the model's abstention, `CITATION_CHECK_FAILED` reports invalid references or figures, and `LLM_UNAVAILABLE` covers generation failures.
- **Cross-language evidence.** The offline German VPN case passes English precedent fixtures to drafting in German. B1's live retrieval results are needed to measure whether the index finds relevant cases across languages.
- **Limitations.** Citation and figure checks verify IDs and amounts. Assessing whether every claim is supported still requires review. The lexicon can overmatch or miss rephrased requests. The 15 demo fixtures exercise B2 decisions with simulated upstream components. Live bilingual output, latency, and A2's threshold recommendations are pending.
