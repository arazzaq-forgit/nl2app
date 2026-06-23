"""
Stage 4: Refinement Layer.
Runs the deterministic consistency checker, then performs TARGETED repair --
only the broken layer is regenerated, with the specific issues fed back to the model
as context. This avoids blind full-pipeline retries.
"""
import json
from app.validators.consistency import check_consistency, Inconsistency
from app.pipeline.llm_client import call_structured, MODEL_STRONG
from app.schemas.models import UISchema, APISchema, DBSchema, AuthSchema, RepairLogEntry

MAX_REPAIR_ROUNDS = 3

REPAIR_SYSTEM_TEMPLATE = """You previously generated the {layer} schema for an app, but it has
consistency issues with the other layers (UI/API/DB/Auth). Fix ONLY what's needed to resolve
the listed issues, keep everything else you generated intact, and return the corrected {layer}
schema as raw JSON matching the required structure."""

LAYER_SCHEMA = {"ui": UISchema, "api": APISchema, "db": DBSchema, "auth": AuthSchema}


def _repair_layer(layer: str, current_value: dict, architecture: dict, issues: list[Inconsistency]) -> dict:
    issue_text = "\n".join(f"- {i.message}" for i in issues if i.layer == layer)
    if not issue_text:
        # Issue belongs to a different layer but references this one (e.g. DB missing a table
        # that UI/API expect) -- still give full context so the model can adapt.
        issue_text = "\n".join(f"- [{i.layer}] {i.message}" for i in issues)

    user_prompt = (
        f"Architecture:\n{json.dumps(architecture, indent=2)}\n\n"
        f"Current {layer} schema:\n{json.dumps(current_value, indent=2)}\n\n"
        f"Issues to fix:\n{issue_text}"
    )
    result = call_structured(
        system_prompt=REPAIR_SYSTEM_TEMPLATE.format(layer=layer),
        user_prompt=user_prompt,
        schema=LAYER_SCHEMA[layer],
        model=MODEL_STRONG,
    )
    return result.data


def run(architecture: dict, ui: dict, api: dict, db: dict, auth: dict):
    """
    Returns (ui, api, db, auth, repair_log, total_repair_latency_ms)
    """
    repair_log: list[RepairLogEntry] = []
    total_latency = 0.0
    layers = {"ui": ui, "api": api, "db": db, "auth": auth}

    for round_num in range(MAX_REPAIR_ROUNDS):
        issues = check_consistency(architecture, layers["ui"], layers["api"], layers["db"], layers["auth"])
        if not issues:
            break

        # Group issues by the layer most likely responsible and repair only those layers.
        affected_layers = sorted({i.layer for i in issues})
        for layer in affected_layers:
            import time
            start = time.time()
            try:
                layers[layer] = _repair_layer(layer, layers[layer], architecture, issues)
                total_latency += (time.time() - start) * 1000
                repair_log.append(RepairLogEntry(
                    stage=layer, issue=f"{len(issues)} issue(s) in round {round_num+1}", action="regenerated"
                ))
            except Exception as e:
                repair_log.append(RepairLogEntry(stage=layer, issue=str(e), action="unresolved"))

    # final check, log anything still unresolved
    final_issues = check_consistency(architecture, layers["ui"], layers["api"], layers["db"], layers["auth"])
    for issue in final_issues:
        repair_log.append(RepairLogEntry(stage=issue.layer, issue=issue.message, action="unresolved"))

    return layers["ui"], layers["api"], layers["db"], layers["auth"], repair_log, total_latency
