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

## Failure handling

- **Vague prompts**: the Intent stage fills gaps with explicit, logged assumptions
  (`assumptions: [...]` field) rather than silently failing or guessing without a trace.
- **Conflicting prompts**: flagged as `ambiguous: true` with an explanation in
  `ambiguity_notes`. If the conflict is severe enough that no entities could be extracted,
  the pipeline halts early with `status: "needs_clarification"` instead of generating a
  broken downstream schema.
- **Schema/consistency failures**: handled by the Stage 4 targeted repair loop, capped at
  3 rounds. Anything still unresolved after that is logged in `repair_log` with
  `action: "unresolved"` and surfaced in the API response as
  `status: "ok_with_warnings"`.

## Cost vs quality tradeoff

See `eval/eval_report.md` after running the eval suite for real numbers. Design choices:
- Cheaper/faster model for Intent Extraction (simple parsing task, low risk of cost from
  errors propagating, since downstream stages can still catch issues).
- Stronger model for architecture + schema generation (harder reasoning, errors here are
  more expensive to repair later).
- Repair rounds capped at 3 to bound worst-case cost/latency on a single request.

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

