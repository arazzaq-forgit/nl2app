"""
Evaluation harness. Runs the full dataset (10 real + 10 edge cases) through the pipeline
and logs: success/fail, repair rounds triggered, failure type, total latency.
Outputs a markdown table + raw JSON log -- "show actual metrics, not claims."
"""
import json
import time
import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.pipeline.orchestrator import run_pipeline

def classify_result(result: dict) -> str:
    status = result.get("status")
    if status == "needs_clarification":
        return "clarification_needed"
    if status == "ok":
        return "success_clean"
    if status == "ok_with_warnings":
        return "success_with_unresolved_repairs"
    return "unknown"


def run_eval():
    with open(os.path.join(os.path.dirname(__file__), "dataset.json")) as f:
        dataset = json.load(f)

    rows = []
    all_prompts = (
        [("real", p) for p in dataset["real_prompts"]]
        + [("edge_vague", p) for p in dataset["edge_cases"]["vague"]]
        + [("edge_conflicting", p) for p in dataset["edge_cases"]["conflicting"]]
        + [("edge_incomplete", p) for p in dataset["edge_cases"]["incomplete"]]
    )

    for category, prompt in all_prompts:
        start = time.time()
        try:
            result = run_pipeline(prompt)
            latency = (time.time() - start) * 1000
            outcome = classify_result(result)
            repairs = len([r for r in result.get("repair_log", []) if r["action"] == "regenerated"])
            unresolved = len([r for r in result.get("repair_log", []) if r["action"] == "unresolved"])
            rows.append({
                "category": category,
                "prompt": prompt[:60],
                "outcome": outcome,
                "repairs_triggered": repairs,
                "unresolved_issues": unresolved,
                "latency_ms": round(latency, 1),
            })
        except Exception as e:
            latency = (time.time() - start) * 1000
            rows.append({
                "category": category,
                "prompt": prompt[:60],
                "outcome": "exception",
                "repairs_triggered": 0,
                "unresolved_issues": -1,
                "latency_ms": round(latency, 1),
                "error": str(e),
            })

    # write raw log
    with open(os.path.join(os.path.dirname(__file__), "eval_results.json"), "w") as f:
        json.dump(rows, f, indent=2)

    # write markdown summary
    total = len(rows)
    successes = len([r for r in rows if r["outcome"] in ("success_clean", "success_with_unresolved_repairs")])
    avg_latency = sum(r["latency_ms"] for r in rows) / total
    avg_repairs = sum(r["repairs_triggered"] for r in rows) / total

    md = [
        "# Evaluation Results\n",
        f"- Total prompts: {total}",
        f"- Success rate: {successes}/{total} ({successes/total*100:.0f}%)",
        f"- Avg latency: {avg_latency:.0f} ms",
        f"- Avg repair rounds triggered: {avg_repairs:.2f}\n",
        "| Category | Prompt | Outcome | Repairs | Unresolved | Latency (ms) |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        md.append(
            f"| {r['category']} | {r['prompt']} | {r['outcome']} | {r['repairs_triggered']} | "
            f"{r['unresolved_issues']} | {r['latency_ms']} |"
        )
    with open(os.path.join(os.path.dirname(__file__), "eval_report.md"), "w") as f:
        f.write("\n".join(md))

    print("\n".join(md))


if __name__ == "__main__":
    run_eval()
