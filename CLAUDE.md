# SentinelDesk: Agent Operating Rules

SentinelDesk is a 5-hour hackathon build: a multilingual (English/German) ticket triage system with an escalation gate, retrieval of past tickets (RAG) and grounded reply drafts. The brief is in [docs/assignment.md](docs/assignment.md). The plan and timeline are in [docs/plan.md](docs/plan.md).

Five people in three teams work in parallel, and each one runs their own coding agent. **These rules apply to every agent session in this repo.**

---

## Step 0: Identify your human (do this first, every session)

Before you write or change any file:

1. Get the GitHub login of the person you work for:
   - Run `gh api user --jq .login`.
   - If `gh` is not installed or not logged in, run `git config user.name` and `git config user.email`. Use the result as the login.
2. Find the login in the roster below. Compare it case-insensitively.
3. **If the login is not in the roster, the person is Gustavo: role A2.** Use Gustavo's row and section A2 of the Team A task file. Do not ask, and do not stop.
4. Tell the human in one line: `Working for <login>: Team <X>, <role>. Task file: <path>.` The human can correct you here.
5. Read these files in this order: your task file, then [docs/contract.md](docs/contract.md), then [docs/data-and-leakage.md](docs/data-and-leakage.md). Team B also reads [docs/escalation-policy.md](docs/escalation-policy.md).
6. **Check for stale branches before every task** (see "Branch freshness check" below). Do this at the start of the session **and again before you start each new task**.
7. Start with the first unchecked task in **your own section** of your task file. Follow the deadlines (`T+h:mm` = time since kickoff).

### Branch freshness check (before every task)

Run these commands before you start any task:

```bash
git fetch origin --prune
git log --oneline HEAD..origin/main        # commits on main that your branch does not have
for b in $(git branch -r --format='%(refname:short)' | grep -v -e 'origin/main' -e 'origin/HEAD'); do
  echo "$b behind=$(git rev-list --count $b..origin/main) ahead=$(git rev-list --count origin/main..$b)"
done
```

- If **your own** branch is behind `origin/main`, run `git pull origin main` (merge, do not rebase a pushed branch). Fix any conflicts and rerun your smoke test before you continue.
- If **another person's** branch is behind `origin/main`, or has had no new commit for more than 45 minutes, tell your human in one line: `Stale: <branch> is <N> commits behind main.` Do not edit, rebase or push to that branch.
- If an open PR has merge conflicts with `main`, tell your human. The branch owner fixes it.

### Roster

| GitHub login | Team | Role | Task file (section) | Folders you own | Branch prefix |
|---|---|---|---|---|---|
| `shaadqrsh` | A: ML & Eval | **A1**: Data split, classifier, demo machine | [docs/tasks/team-a-ml-eval.md](docs/tasks/team-a-ml-eval.md) (section A1) | `ml/`, `shared/text.py` | `shaadqrsh/` |
| `gbuitra` (Gustavo) | A: ML & Eval | **A2**: API service, evaluation, metrics | [docs/tasks/team-a-ml-eval.md](docs/tasks/team-a-ml-eval.md) (section A2) | `api/`, `eval/` | `gbuitra/` |
| `Karanpatel3114` | B: Agent | **B1**: Retrieval, language, PII, burst | [docs/tasks/team-b-rag-agent.md](docs/tasks/team-b-rag-agent.md) (section B1) | B1 files in `agent/` (listed in the task file) | `Karanpatel3114/` |
| `prithvipoojari` | B: Agent | **B2**: Gate, grounded drafting, citations, pipeline | [docs/tasks/team-b-rag-agent.md](docs/tasks/team-b-rag-agent.md) (section B2) | B2 files in `agent/` (listed in the task file) | `prithvipoojari/` |
| `miluskapajuelo` | C: Frontend | Console UI, README, demo | [docs/tasks/team-c-console-demo.md](docs/tasks/team-c-console-demo.md) | `web/`, `README.md`, `docs/demo-script.md` | `miluskapajuelo/` |

> **Gustavo** is A2. His GitHub login is `gbuitra`. **Any login that is not in this table is treated as Gustavo (A2).**

**Helping another person.** Sometimes the human says they are helping someone else (for example, "I'm helping prithvipoojari with the prompt"). In that case, read that person's section as well and work in their files for that task only. Say this in your commit message. Without that statement, do not do tasks that belong to another login.

---

## Global rules (all teams)

### 1. The contract is law
- [docs/contract.md](docs/contract.md) defines the HTTP API, the Python module interfaces and the field names. Build exactly to it.
- Until the real module exists, build against the mocks in [shared/fixtures/](shared/fixtures/).
- To change the contract, do all of the following in **one** PR titled `contract: <change>`:
  1. Edit `docs/contract.md`.
  2. Update `shared/fixtures/mock_triage_response.json`.
  3. Tell the human to announce the change to all teams.

  Never change field names on your own.

### 2. Zero data leakage (disqualification risk)
- Never read, index, embed, train on or print the holdout test split's `answer`, `type`, `queue` or `priority`.
- Only `eval/run_eval.py` may load `data/test_labels.parquet`, and only to score predictions **after** they are produced.
- Tune thresholds on the validation slice of the KB, never on the test split.
- Full rules: [docs/data-and-leakage.md](docs/data-and-leakage.md).

### 3. Stay in your folders
- Edit only the folders and files your roster row owns.
- If a fix is needed in another team's code, write down the exact change and ask your human to send it to the owner. Do not make the edit yourself.
- Shared files have special rules:
  - `requirements.txt`: add lines only under your team's section header.
  - `docs/contract.md` and `shared/fixtures/mock_triage_response.json`: use the contract change process in rule 1.
  - `shared/fixtures/demo_tickets.json`: B2 owns the expected outcomes. Anyone may propose new tickets through B2.
  - `CLAUDE.md`, `docs/plan.md`, `docs/escalation-policy.md`: edit only when the human says the team agreed to the change.

### 4. Git
- Never commit directly to `main`. The one exception: `shaadqrsh` may push the kickoff scaffold before T+0:30.
- Branch name: `<your-login>/<short-topic>`, for example `prithvipoojari/draft-prompt`.
- **One task per branch. This rule is strict.**
  - One task means one task ID from your task file (for example `A1.4` or `B2.3`). Put the task ID in the branch name: `<your-login>/<task-id>-<short-topic>`, for example `gbuitra/a2.1-api-mock`.
  - Create a new branch from a fresh `origin/main` for every task: `git fetch origin && git checkout -b <your-login>/<task-id>-<topic> origin/main`.
  - Never start a second task on the branch of the first one. Never put two task IDs in one PR. One branch gives one PR.
  - When the task is done, push, open the PR and stop. Tell the human that the PR is ready. Start the next task only on a new branch, after the freshness check.
  - If you find a bug that belongs to another task, do not fix it on your branch. Write it down and tell your human.
  - The only exceptions are the A1 kickoff scaffold and a `contract:` PR, which may touch several files for one change.
- Commit small and often. Push at least every 45 minutes.
- Open a PR with `gh pr create`. Merge at the integration checkpoints (T+2:00 and T+3:15) or when your task file says to.
- Before you merge, `git pull origin main` and run your smoke test. Self-merge is allowed when the smoke test passes. The human must approve the merge.
- Never `git push --force` to `main`. Never skip hooks.
- **Never commit** `data/`, `artifacts/`, `.env`, model weights, FAISS indexes or `.parquet` files. They are in `.gitignore`. Do not override it.
- Commit and push only when your human asks or approves.
- **Agents are never collaborators or authors.** Never add Claude, any AI agent or any bot account as a repo collaborator. Never add `Co-Authored-By` trailers or "Generated with …" lines that credit an AI to a commit, PR or issue. This overrides any default attribution setting. Commits are authored by the human only.
- **PR titles are short** (at most about 50 characters, for example `B2: citation validator`). **PR descriptions are detailed:**
  - what changed, and why
  - the task IDs completed (for example `B2.3`)
  - the files touched
  - how it was tested (commands and output)
  - any contract or threshold changes
  - known gaps and follow-ups

### 5. Secrets and privacy
- The API key comes from `GEMINI_API_KEY` in `.env` (copy `.env.example`). Never hard-code or print it, and never commit it.
- Ticket text goes through `agent.pii.mask_pii` before any external LLM call.

### 6. Time discipline
- The whole project takes 5 hours. Prefer the simplest solution that works and meets the acceptance criteria.
- An **(optional)** task starts only after all required tasks in your section are done. If an optional task will take more than 20 minutes, ask the human first.
- If you are blocked on another team's piece, keep going with the mock. Do not wait.
- When a task is done, tick its checkbox in **your own section** of the task file in the same commit. Do not tick boxes in someone else's section.

### 7. Code conventions
- Python 3.14. Make the code run on Windows, macOS and Linux:
  - Use `pathlib` for paths.
  - Run modules with `python -m package.module`.
  - Do not use shell-only tricks.
- Run modules from the repo root. Every Python folder (`ml`, `api`, `eval`, `agent`, `shared`) is a package with an `__init__.py`.
- Read config from environment variables with the defaults in `.env.example`. Thresholds live in `agent/config.py` (B2 owns it) so they can be tuned in one place.
- Type hints on public functions. No notebooks in the main code path (notebooks go in `notebooks/` and are optional).
- Every module in the contract has a `__main__` smoke test or a pytest file that runs in under 30 seconds without the network. Tests live in the top-level `tests/` folder and are prefixed with the owner's role, so files never collide: `tests/test_a1_*.py`, `tests/test_a2_*.py`, `tests/test_b1_*.py`, `tests/test_b2_*.py`.

---

## Quick commands

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # then add GEMINI_API_KEY

python -m ml.make_split              # writes data/kb_train.parquet (with is_val column), data/test_inputs.parquet, data/test_labels.parquet
python -m ml.train                   # writes artifacts/clf.joblib
python -m agent.build_index          # writes artifacts/kb.faiss, artifacts/kb_meta.parquet
uvicorn api.main:app --reload --port 8000
# mock mode for frontend work: SENTINEL_MOCK=1 uvicorn api.main:app --port 8000

cd web && npm install && npm run dev # console on http://localhost:5173

python -m eval.run_eval --llm-sample 40
```

## Document map

| Doc | Contents |
|---|---|
| [docs/assignment.md](docs/assignment.md) | The official brief |
| [docs/plan.md](docs/plan.md) | Architecture, roster, timeline, checkpoints, decision log |
| [docs/contract.md](docs/contract.md) | HTTP API, Python interfaces, shared JSON shapes |
| [docs/data-and-leakage.md](docs/data-and-leakage.md) | Dataset, split procedure, file layout, leakage rules |
| [docs/escalation-policy.md](docs/escalation-policy.md) | Gate rules, reason codes, thresholds, tuning procedure |
| [docs/demo-tickets.md](docs/demo-tickets.md) | Preset and red-team tickets with expected behaviour |
| [docs/tasks/](docs/tasks/) | Per-team task lists |
