# **SentinelDesk \- Autonomous Incident Triage & Grounded Resolution Copilot**

**Time Limit:** 6 Hours Maximum  
**Track:** Applied AI, NLP, Retrieval-Augmented Generation (RAG) & Agentic Workflows  
Permitted Tech Stack: Open-source models, commercial LLM APIs, classical ML, vector databases, and any frontend/backend framework

# **1\. Background & Real-World Context**

Enterprise IT helpdesks and technical operations teams process thousands of incoming tickets daily across multiple languages, spanning routine password resets, pre-sales product inquiries, billing disputes, and mission-critical infrastructure outages.

Operations teams currently struggle with two failure modes:

* **Triage Bottlenecks & Missed Outages:** Critical high-priority incidents—such as a VPN failure cutting off hospital telemedicine and EMR integrations—arrive in the same unstructured inbox as low-priority feature questions, delaying escalation by hours.  
* **LLM Hallucinations in Auto-Replies:** Off-the-shelf generative AI chatbots draft fluent responses, but routinely invent unsupported product integrations, fabricate SLA refund guarantees, or give unsafe troubleshooting instructions ungrounded in historical company resolutions.

# **2\. Your 6-Hour Mission**

Design and build SentinelDesk, an end-to-end Multilingual Incident Triage, Smart Escalation, and Precedent-Grounded Resolution Copilot.

When a raw incoming ticket (subject \+ body) arrives, your system must automatically:

* **Classify & Prioritize:** Predict the ticket's `type`, target `queue` (department), and `priority` (`high`, `medium`, `low`), alongside a calibrated confidence score.  
* **Apply an Escalation & Safety Gate:** Decide whether the ticket can be safely answered with an AI-drafted reply or must be immediately flagged for **Human Escalation** (for example: high-priority outages, low model confidence, or out-of-scope requests with no historical precedent).  
* **Retrieve Historical Precedents (RAG):** Search past resolved tickets to surface the top 3 to 5 most relevant historical cases and resolutions.  
* **Draft a Grounded Multilingual Reply:** Generate a concise, professional draft response in the requester's native language (English or German) strictly grounded in retrieved historical resolutions, explicitly referencing which past ticket IDs informed the draft.

# **3\. Official Dataset (Free & Open Access)**

All teams must use the publicly available **Customer Support Tickets Dataset** hosted on Hugging Face. No account payment, subscription, or proprietary data access is required.

* **Dataset Page & Direct Download:** [Customer Support Tickets Dataset on Hugging Face (Tobi-Bueck/customer-support-tickets)](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets)  
* **License:** Creative Commons Attribution-NonCommercial 4.0 (CC-BY-NC-4.0)  
* **Volume & Size:** \~61,800 tickets (\~26 MB to 53 MB CSV files — downloads in under 15 seconds)  
* **Recommended File:** `aa_dataset-tickets-multi-lang-5-2-50-version.csv` (or the 20k subset `dataset-tickets-multi-lang-4-20k.csv` for faster rapid prototyping)

## **Dataset Schema**

| Column | Data Type | Role at Inference Time | Description |
| :---- | :---- | :---- | :---- |
| `subject` | String (nullable) | **Input** | Ticket subject line. *Note: Some rows contain null/empty subjects—your pipeline must handle missing subjects without crashing.* |
| `body` | String | **Input** | Full unstructured customer message (primarily English `en` and German `de`). |
| `type` | Categorical | **Target to Predict** | Four classes: `Incident`, `Request`, `Problem`, `Change`. |
| `queue` | Categorical | **Target to Predict** | Routing department (e.g., `Technical Support`, `Product Support`, `Billing and Payments`, `Customer Service`, `IT Support`, `Sales and Pre-Sales`). |
| `priority` | Categorical | **Target to Predict** | Urgency level: `high`, `medium`, `low`. |
| `language` | String | **Metadata / Target** | Language code (`en`, `de`). At live demo time, your system must detect language automatically from raw text. |
| `tag_1` .. `tag_8` | String (nullable) | **Optional Auxiliary** | Issue keywords/tags useful for clustering or metadata filtering. |
| `answer` | String | **Historical KB Only** | Official resolution written by a support agent. **Strict Leakage Rule:** You may index `answer` ONLY for your historical training/knowledge-base split (e.g., 80% split). Never pass or index the holdout test set's `answer` column\! |

## **Quick-Start Python Loading Snippet**

`from datasets import load_dataset`  
`import pandas as pd`

`# Option A: Load directly via Hugging Face datasets library`  
`ds = load_dataset("Tobi-Bueck/customer-support-tickets")`  
`df = ds["train"].to_pandas()`

`# Create a strict 80/20 split: 80% Historical Knowledge Base & Training, 20% Unseen Holdout Test`  
`df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)`  
`df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]`

`split_idx = int(len(df) * 0.8)`  
`kb_train_df = df.iloc[:split_idx].copy()   # Allowed for training & RAG vector indexing`  
`test_df = df.iloc[split_idx:].copy()       # Holdout evaluation ONLY (hide labels & answers at inference!)`

# **4\. Core Functional Deliverables (Required MVP)**

To complete the challenge within 8 hours, your submission must demonstrate four working components:

* **Multi-Task Triage Engine:**  
  * Given raw `subject` (optional) and `body`, output predicted `type`, `queue`, and `priority` with confidence scores.  
  * Report quantitative holdout metrics on your 20% test split (Macro-F1 across classes, plus **High-Priority Incident Recall**).  
* **Confidence & Risk Escalation Gate:**  
  * Define explicit logic that routes tickets to **Human Review / Immediate Escalation** when `priority == high` and `type == Incident`, when classifier/retrieval similarity falls below a threshold, or when a user asks for actions unsupported by historical resolutions.  
* **Evidence-Backed Resolution Generator (RAG):**  
  * Index the historical `kb_train_df` tickets and retrieve top-k similar past tickets.  
  * Generate a tailored response in the user's language (`en` or `de`) that cites the retrieved `ticket_id` records and refuses to fabricate policies, pricing numbers, or legal guarantees not supported by retrieved evidence.  
* **Live Triage Console (Interactive Demo UI):**  
  * Build a clean operator dashboard (Streamlit, Gradio, Next.js, FastAPI, etc.) where judges can paste custom, unseen tickets in real time and inspect:  
    * Predicted `type`, `queue`, `priority`, confidence score, and end-to-end latency.  
    * Escalation status badge (`Auto-Draft Ready` vs. `Escalate to On-Call Engineer` with reason).  
    * Top retrieved historical tickets (`ticket_id`, similarity score, historical `answer` snippet).  
    * Generated draft response.

# **5\. Optional Bonus Features (If Time Permits)**

* **Cross-Lingual Precedent Matching:** Retrieve relevant English historical resolutions to help answer a German ticket (or vice versa) while outputting the final reply in the user's language.  
* **Live Outage / Burst Detection:** Detect when multiple incoming tickets describe the same underlying system failure (e.g., cluster of VPN or login failures) and raise a "Major Incident Outage Banner."  
* **PII Guardrail:** Automatically mask emails, phone numbers, IP addresses, or account numbers before sending ticket text to external LLM APIs.

# **6\. Suggested 6-Hour Pacing Guide**

* **Hour 0:00 – 1:00 \| Data Exploration & Split Setup:** Download dataset, inspect class imbalance and null `subject` rows, lock your 80/20 `kb_train_df` / `test_df` split, and align team roles.  
* **Hour 1:00 – 2:00\| Triage Classifier & Vector Store:** Build a fast baseline classifier (e.g., fine-tuned DeBERTa/DistilBERT, TF-IDF \+ LightGBM, or structured embeddings) and index `kb_train_df` in FAISS, Chroma, Qdrant, or pgvector.  
* **Hour 2:00 – 4:00 \| Grounded RAG & Escalation Guardrails:** Connect retrieval to your LLM prompt, enforce `ticket_id` citations, implement abstention/escalation rules for ungrounded queries, and test German \+ English generation.  
* **Hour 4:00 – 5:00 \| Operator UI & Holdout Evaluation:** Build the interactive triage console, run batch evaluation on a test sample to compute Macro-F1 and latency, and test edge cases (empty subjects, adversarial prompts).  
* **Hour 5:00 – 6:00 \| Feature Freeze & Demo Prep:** Freeze code, write a concise `README.md`, and rehearse a crisp 5-minute live demonstration.

# **7\. Submission Requirements & Fair-Play Rules**

* **Zero Data Leakage:** Indexing or reading the holdout test split's `answer`, `queue`, `type`, or `priority` during evaluation will result in disqualification or point penalties.  
* **Code Repository:** Link to a public or judge-accessible Git repository containing source code, `requirements.txt` / environment setup, and evaluation script.  
* **5-Minute Live Demo \+ 3-Minute Judge Q\&A:** Judges will test your live UI using unseen real-time prompts during Q\&A. Slide-only submissions without working code will not be eligible for top prizes.

