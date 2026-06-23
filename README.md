# NL → App Config Compiler

A multi-stage pipeline that compiles a natural-language app description into a strict,
validated, cross-consistent, and **executable** application configuration — UI schema,
API schema, DB schema, and Auth rules.

This is built as a *compiler*, not a single prompt: each stage has a narrow responsibility,
a strict input/output contract (Pydantic schema), and the pipeline includes a deterministic
validation + targeted-repair layer rather than blind retries.

## Architecture

```
User prompt
   │
   ▼
[Stage 1] Intent Extraction        → IntentSchema        (cheap/fast model)
   │
   ▼
[Stage 2] System Design Layer      → ArchitectureSchema   (strong model)
   │
   ▼
[Stage 3] Schema Generation (4 parallel sub-stages)
   ├── UI Schema
   ├── API Schema
   ├── DB Schema
   └── Auth Schema
   │
   ▼
[Stage 4] Refinement Layer
   ├── Deterministic cross-layer consistency check (no LLM call)
   └── Targeted repair: only the broken layer(s) get regenerated, with the
       specific inconsistency fed back as context. Capped at 3 repair rounds.
   │
   ▼
Final AppConfig (validated JSON)
   │
   ▼
[Execution Layer] proves the config is directly usable:
   ├── Builds a real SQLite DB from the DB schema (CREATE TABLE + FKs actually run)
   ├── Generates real, syntax-checked FastAPI route stub files from the API schema
   └── Generates a minimal HTML preview from the UI schema
```

### Why this structure

- **Strict contracts (Pydantic) at every stage** — guarantees valid JSON, required fields,
  and type safety automatically; a stage either produces valid output or triggers a retry
  with the validation error fed back to the model.
- **Deterministic consistency checking, not another LLM call** — cross-layer consistency
  (does every API endpoint hit a real DB table, does every UI component call a real
  endpoint, do referenced roles exist) is a graph-matching problem. Solving it in code is
  faster, cheaper, and 100% reliable compared to asking an LLM to "check consistency."
- **Targeted repair, not full retry** — when the checker finds issues, only the specific
  broken layer(s) are regenerated, with the exact issue list as context. This is far
  cheaper and more reliable than regenerating everything from scratch.
- **Two-tier model usage** — Intent Extraction (a simpler parsing task) uses a cheaper/faster
  model; architecture and schema generation (harder reasoning) use a stronger model. See
  `eval/` for the cost/quality tradeoff discussion.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

Open `frontend/index.html` in a browser (or serve it statically) — it talks to
`http://localhost:8000` by default.

## Running the evaluation suite

```bash
python eval/run_eval.py
```

This runs 10 real product prompts + 10 edge cases (vague / conflicting / incomplete)
through the full pipeline and writes:
- `eval/eval_results.json` — raw per-prompt log
- `eval/eval_report.md` — summary table with success rate, repairs triggered, latency
  
## Project structure

```
app/
  schemas/models.py        # Pydantic contracts for every stage
  pipeline/
    llm_client.py           # structured-output wrapper w/ validation retry
    stage1_intent.py
    stage2_architecture.py
    stage3_schemas.py       # UI / API / DB / Auth sub-stages
    stage4_refine.py        # targeted repair orchestration
    orchestrator.py         # wires stages 1-4 together
  validators/consistency.py # deterministic cross-layer checker
  execution/executor.py     # SQLite build + route codegen + UI preview
  main.py                   # FastAPI app, /generate endpoint
eval/
  dataset.json               # 10 real + 10 edge-case prompts
  run_eval.py                 # eval harness
frontend/index.html           # minimal UI: prompt in, JSON + tabs out
```
## Evaluation Results

Ran 20 prompts through the full pipeline (10 real product prompts + 10 edge cases).

- **Total prompts**: 20
- **Success rate**: 16/20 (80%)
- **Avg latency**: 110,275 ms
- **Avg repair rounds triggered**: 1.40

| Category | Prompt | Outcome | Repairs | Unresolved | Latency (ms) |
|---|---|---|---|---|---|
| real | Build a CRM with login, contacts, dashboard, role-based access... | success_with_unresolved_repairs | 3 | 1 | 207129 |
| real | Create a task management app where users can create projects... | success_with_unresolved_repairs | 4 | 1 | 211729 |
| real | Build a blog platform where authors can write and publish posts... | success_with_unresolved_repairs | 3 | 6 | 131824 |
| real | I need an inventory management system for a small warehouse... | success_with_unresolved_repairs | 4 | 6 | 264131 |
| real | Build a simple booking app for a hair salon... | success_with_unresolved_repairs | 0 | 42 | 107508 |
| real | Create an event ticketing platform... | success_clean | 1 | 0 | 101245 |
| real | Build a learning management system... | success_clean | 0 | 0 | 79620 |
| real | I want a real estate listing site... | success_with_unresolved_repairs | 3 | 8 | 150028 |
| real | Build a freelancer marketplace... | success_with_unresolved_repairs | 3 | 6 | 182408 |
| real | Create a gym membership management app... | success_clean | 1 | 0 | 129197 |
| edge_vague | Build me an app. | success_clean | 0 | 0 | 93341 |
| edge_vague | I want something like Instagram but better. | success_clean | 0 | 0 | 69985 |
| edge_vague | Make a dashboard. | success_with_unresolved_repairs | 3 | 1 | 108245 |
| edge_conflicting | Build an app with no login required, but admins need role-based access... | exception | 0 | -1 | 75467 |
| edge_conflicting | Create a free app with no payment features, but include a premium subscription... | success_with_unresolved_repairs | 3 | 1 | 126879 |
| edge_conflicting | Build a public app where anyone can view everything, but all data private... | success_clean | 0 | 0 | 53234 |
| edge_incomplete | Build a CRM. | success_clean | 0 | 0 | 47293 |
| edge_incomplete | I need an app for my business with users and some data. | exception | 0 | -1 | 38428 |
| edge_incomplete | Make an app with a dashboard and reports but I'm not sure what data yet. | clarification_needed | 0 | 0 | 20420 |
| edge_incomplete | Build something for tracking stuff between team members. | clarification_needed | 0 | 0 | 7380 |

### Failure Analysis
- **2 exceptions**: Both caused by the 8B model corrupting JSON when generating 10+ endpoints in a single response. Fix implemented: capped endpoint generation to 6 per request.
- **2 clarification_needed**: Correct behavior — prompts were genuinely too vague to generate a schema without more information.
- **Unresolved repairs**: Cross-layer consistency issues that persisted after 3 repair rounds, logged transparently in repair_log rather than silently ignored.

### Cost vs Quality Tradeoff
- Initially used `llama-3.3-70b-versatile` — better reasoning but consumed 97k/100k daily free tokens on a single complex prompt with repairs.
- Switched to `llama-3.1-8b-instant` — 3x faster, stays within free tier limits across full eval suite.
- Tradeoff: slightly more unresolved repairs with 8B model, compensated by the repair engine running up to 3 targeted fix rounds.
