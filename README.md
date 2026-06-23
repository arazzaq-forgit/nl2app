# NL → App Config Compiler

A multi-stage pipeline that compiles a natural-language app description into a strict,
validated, cross-consistent, and **executable** application configuration — UI schema,
API schema, DB schema, and Auth rules.

This is built as a *compiler*, not a single prompt: each stage has a narrow responsibility,
a strict input/output contract (Pydantic schema), and the pipeline includes a deterministic
validation + targeted-repair layer rather than blind retries.

## Architecture
User prompt

│

▼

[Stage 1] Intent Extraction        → IntentSchema        (fast model)

│

▼

[Stage 2] System Design Layer      → ArchitectureSchema   (strong model)

│

▼

[Stage 3] Schema Generation (4 independent sub-stages)

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

├── Builds a real SQLite DB from the DB schema

├── Generates real, syntax-checked FastAPI route stub files

└── Generates a minimal HTML preview from the UI schema
## Why this structure

- **Strict contracts (Pydantic) at every stage** — guarantees valid JSON, required fields,
  and type safety automatically
- **Deterministic consistency checking, not another LLM call** — cross-layer consistency
  is a graph-matching problem, solved in code not prompts
- **Targeted repair, not full retry** — only broken layers are regenerated with the exact
  issue list as context
- **Two-tier model usage** — faster model for Intent Extraction, stronger model for
  architecture and schema generation

## Live Demo

**Frontend**: https://voluble-gumption-ccc447.netlify.app
**Backend**: https://nl2app.onrender.com  
**GitHub**: https://github.com/arazzaq-forgit/nl2app

## Setup

```bash
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY
uvicorn app.main:app --reload
```

Open `frontend/index.html` in a browser pointed at `http://localhost:8000`.

## Running the evaluation suite

```bash
python eval/run_eval.py
```

Runs 20 prompts through the full pipeline and writes:
- `eval/eval_results.json` — raw per-prompt log
- `eval/eval_report.md` — summary table

## Evaluation Results

Ran 20 prompts (10 real product prompts + 10 edge cases: vague, conflicting, incomplete).

- **Total prompts**: 20
- **Success rate**: 17/20 (85%)
- **Avg latency**: 170,593 ms
- **Avg repair rounds triggered**: 3.30

| Category | Prompt | Outcome | Repairs | Unresolved | Latency (ms) |
|---|---|---|---|---|---|
| real | Build a CRM with login, contacts, dashboard, role-based access... | success_with_unresolved_repairs | 3 | 10 | 160998 |
| real | Create a task management app where users can create projects... | success_with_unresolved_repairs | 6 | 12 | 287169 |
| real | Build a blog platform where authors can write and publish posts... | success_with_unresolved_repairs | 3 | 6 | 156450 |
| real | I need an inventory management system for a small warehouse... | success_with_unresolved_repairs | 3 | 4 | 176413 |
| real | Build a simple booking app for a hair salon... | success_with_unresolved_repairs | 3 | 8 | 147282 |
| real | Create an event ticketing platform... | success_with_unresolved_repairs | 6 | 9 | 346805 |
| real | Build a learning management system... | success_with_unresolved_repairs | 6 | 12 | 194331 |
| real | I want a real estate listing site... | success_with_unresolved_repairs | 4 | 10 | 208304 |
| real | Build a freelancer marketplace... | success_with_unresolved_repairs | 6 | 5 | 276906 |
| real | Create a gym membership management app... | success_clean | 5 | 1 | 246432 |
| edge_vague | Build me an app. | exception | 0 | -1 | 80196 |
| edge_vague | I want something like Instagram but better. | success_clean | 1 | 0 | 96418 |
| edge_vague | Make a dashboard. | success_with_unresolved_repairs | 3 | 2 | 107760 |
| edge_conflicting | Build an app with no login required, but admins need role-based access... | success_with_unresolved_repairs | 3 | 5 | 113848 |
| edge_conflicting | Create a free app with no payment features, but include a premium subscription... | success_with_unresolved_repairs | 3 | 5 | 204269 |
| edge_conflicting | Build a public app where anyone can view everything, but all data private... | success_with_unresolved_repairs | 3 | 5 | 189211 |
| edge_incomplete | Build a CRM. | success_clean | 0 | 0 | 91642 |
| edge_incomplete | I need an app for my business with users and some data. | exception | 0 | -1 | 65766 |
| edge_incomplete | Make an app with a dashboard and reports but I'm not sure what data yet. | clarification_needed | 0 | 0 | 9403 |
| edge_incomplete | Build something for tracking stuff between team members. | success_with_unresolved_repairs | 8 | 8 | 252248 |

## Failure Analysis

- **2 exceptions**: JSON corruption when model generates complex schemas — root cause identified, fix implemented (endpoint cap at 6)
- **1 clarification_needed**: Correct behavior — prompt too vague to generate a schema
- **Unresolved repairs**: Cross-layer consistency issues logged transparently in repair_log rather than silently ignored

## Cost vs Quality Tradeoff

- Started with `llama-3.3-70b-versatile` — better reasoning but consumed 97k/100k daily free tokens on a single complex prompt with repairs
- Switched to `llama-3.1-8b-instant` — faster, stays within free tier limits across full eval suite
- Tradeoff: more unresolved repairs with 8B model, compensated by repair engine running up to 3 targeted fix rounds
- In production: use stronger model for architecture/schema stages, faster model for intent extraction

## Failure Handling

- **Vague prompts**: fills gaps with explicit documented assumptions (`assumptions: []` field)
- **Conflicting prompts**: flagged as `ambiguous: true` with explanation in `ambiguity_notes`
- **Unresolvable**: returns `status: needs_clarification` instead of generating broken schema

## 📁 Project Structure

```
nl2app/
│
├── 🧠 app/
│   │
│   ├── 🔄 pipeline/
│   │   ├── llm_client.py          # LLM wrapper — validation + rate-limit retry
│   │   ├── stage1_intent.py       # Stage 1 — Natural language → Intent
│   │   ├── stage2_architecture.py # Stage 2 — Intent → Architecture
│   │   ├── stage3_schemas.py      # Stage 3 — UI / API / DB / Auth schemas
│   │   ├── stage4_refine.py       # Stage 4 — Targeted repair engine
│   │   └── orchestrator.py        # Wires all 4 stages together
│   │
│   ├── 📐 schemas/
│   │   └── models.py              # Pydantic contracts for every stage
│   │
│   ├── ✅ validators/
│   │   └── consistency.py         # Deterministic cross-layer checker (no LLM)
│   │
│   ├── ⚙️ execution/
│   │   └── executor.py            # SQLite + FastAPI routes + HTML preview
│   │
│   └── 🚀 main.py                 # FastAPI server — /generate endpoint
│
├── 📊 eval/
│   ├── dataset.json               # 20 test prompts (10 real + 10 edge cases)
│   └── run_eval.py                # Evaluation harness — metrics + reporting
│
├── 🌐 frontend/
│   └── index.html                 # Single page UI — prompt in, JSON out
│
├── 📋 requirements.txt
└── 🔑 .env.example
```tor.py          # wires all stages together

validators/consistency.py  # deterministic cross-layer checker

execution/executor.py      # SQLite + route codegen + UI preview

main.py                    # FastAPI app

eval/

dataset.json               # 10 real + 10 edge-case prompts

run_eval.py                # eval harness

frontend/index.html          # minimal UI
