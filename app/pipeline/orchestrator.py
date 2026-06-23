"""
Orchestrator: runs Stage 1 -> 2 -> 3 (sub-stages) -> 4, assembling the final AppConfig.
This is the only place that knows about the full pipeline order -- each stage module
only knows about its own input/output contract.
"""
import time
from app.pipeline import stage1_intent, stage2_architecture, stage3_schemas, stage4_refine
from app.schemas.models import AppConfig


def run_pipeline(user_text: str) -> dict:
    latencies = {}

    intent, lat, retries = stage1_intent.run(user_text)
    latencies["intent"] = lat

    # Conflicting/unresolvable prompts stop early with a clear failure reason rather than
    # producing a garbage downstream schema.
    if intent.get("ambiguous") and not intent.get("entities"):
        return {
            "status": "needs_clarification",
            "intent": intent,
            "message": intent.get("ambiguity_notes", "Prompt too ambiguous to proceed."),
            "stage_latencies_ms": latencies,
        }

    architecture, lat, retries = stage2_architecture.run(intent)
    latencies["architecture"] = lat

    ui, lat, _ = stage3_schemas.run_ui(architecture)
    latencies["ui"] = lat
    api, lat, _ = stage3_schemas.run_api(architecture)
    latencies["api"] = lat
    db, lat, _ = stage3_schemas.run_db(architecture)
    latencies["db"] = lat
    auth, lat, _ = stage3_schemas.run_auth(architecture)
    latencies["auth"] = lat

    start = time.time()
    ui, api, db, auth, repair_log, repair_latency = stage4_refine.run(architecture, ui, api, db, auth)
    latencies["refinement"] = repair_latency

    config = AppConfig(
        intent=intent,
        architecture=architecture,
        ui=ui,
        api=api,
        db=db,
        auth=auth,
        repair_log=repair_log,
        stage_latencies_ms=latencies,
    )

    unresolved = [r for r in repair_log if r.action == "unresolved"]
    result = config.model_dump()
    result["status"] = "ok" if not unresolved else "ok_with_warnings"
    return result
