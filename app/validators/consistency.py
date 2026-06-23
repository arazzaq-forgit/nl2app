"""
Deterministic cross-layer consistency checker.
Runs WITHOUT calling an LLM -- pure code -- to catch drift between UI/API/DB/Auth.
This is intentionally not an LLM call: consistency checking is a graph-matching problem,
not a generation problem, and deterministic code is faster, cheaper, and more reliable for it.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Inconsistency:
    layer: str          # "ui" | "api" | "db" | "auth"
    severity: str        # "error" | "warning"
    message: str
    target_id: str = ""  # id of the offending component/endpoint/table, for targeted repair


def check_consistency(architecture: dict, ui: dict, api: dict, db: dict, auth: dict) -> List[Inconsistency]:
    issues: List[Inconsistency] = []

    table_names = {t["name"] for t in db["tables"]}
    entity_names = {e["name"] for e in architecture["entities"]}
    role_names = {r["name"] for r in auth["roles"]}
    endpoint_ids = {e["id"] for e in api["endpoints"]}

    # 1. Every architecture entity should have a backing DB table.
    for ent in entity_names:
        if ent not in table_names:
            issues.append(Inconsistency("db", "error", f"Entity '{ent}' has no matching DB table", ent))

    # 2. Every API endpoint must reference a real DB entity/table.
    for ep in api["endpoints"]:
        if ep["entity"] not in table_names:
            issues.append(Inconsistency(
                "api", "error",
                f"Endpoint '{ep['id']}' references entity '{ep['entity']}' with no matching DB table",
                ep["id"],
            ))
        for r in ep.get("roles_allowed", []):
            if r not in role_names:
                issues.append(Inconsistency(
                    "api", "error",
                    f"Endpoint '{ep['id']}' allows role '{r}' which doesn't exist in auth schema",
                    ep["id"],
                ))

    # 3. Every UI component's api_call must reference a real endpoint id.
    for page in ui["pages"]:
        for comp in page["components"]:
            if comp.get("api_call") and comp["api_call"] not in endpoint_ids:
                issues.append(Inconsistency(
                    "ui", "error",
                    f"Page '{page['name']}' component '{comp['label']}' calls unknown endpoint "
                    f"'{comp['api_call']}'",
                    page["name"],
                ))
        for r in page.get("roles_allowed", []):
            if r not in role_names:
                issues.append(Inconsistency(
                    "ui", "error",
                    f"Page '{page['name']}' allows role '{r}' which doesn't exist in auth schema",
                    page["name"],
                ))

    # 4. Foreign keys in DB must point at real tables.
    for table in db["tables"]:
        for col in table["columns"]:
            if col["type"] == "FOREIGN_KEY":
                if not col.get("foreign_key_table") or col["foreign_key_table"] not in table_names:
                    issues.append(Inconsistency(
                        "db", "error",
                        f"Table '{table['name']}' column '{col['name']}' is a FOREIGN_KEY with "
                        f"invalid/missing target table",
                        table["name"],
                    ))

    return issues
