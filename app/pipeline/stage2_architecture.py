"""Stage 2: System Design Layer — IntentSchema -> ArchitectureSchema."""
import json
from app.schemas.models import ArchitectureSchema
from app.pipeline.llm_client import call_structured, MODEL_STRONG

SYSTEM_PROMPT = """You are the System Design stage of a software-generation compiler.
Convert a structured intent into a concrete app architecture.

Return a JSON object with exactly these fields:
- "entities": array of entity objects
- "roles": array of role permission objects
- "flows": array of plain strings describing user flows

Each entity object must have:
- "name": string
- "fields": array of field objects

Each field object must have:
- "name": string
- "type": one of: "string", "number", "boolean", "date", "enum", "relation"
- "required": boolean
- "enum_values": array of strings or null
- "relation_target": string or null (entity name this relates to)

Each role permission object must have:
- "role": string (the role name)
- "can_access": array of strings (entity or feature names)

Example output:
{
  "entities": [
    {
      "name": "User",
      "fields": [
        {"name": "username", "type": "string", "required": true, "enum_values": null, "relation_target": null},
        {"name": "role", "type": "enum", "required": true, "enum_values": ["admin", "user"], "relation_target": null}
      ]
    },
    {
      "name": "Contact",
      "fields": [
        {"name": "name", "type": "string", "required": true, "enum_values": null, "relation_target": null},
        {"name": "email", "type": "string", "required": true, "enum_values": null, "relation_target": null},
        {"name": "owner", "type": "relation", "required": true, "enum_values": null, "relation_target": "User"}
      ]
    }
  ],
  "roles": [
    {"role": "admin", "can_access": ["Contact", "Analytics", "Dashboard"]},
    {"role": "user", "can_access": ["Contact", "Dashboard"]}
  ],
  "flows": [
    "user signs up -> creates contact -> views dashboard",
    "admin logs in -> views analytics"
  ]
}"""


def run(intent: dict) -> dict:
    user_prompt = (
        f"Structured intent:\n{json.dumps(intent, indent=2)}\n\n"
        f"Generate the architecture for this app. "
        f"Return only a JSON object matching the structure shown in the example."
    )
    result = call_structured(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=ArchitectureSchema,
        model=MODEL_STRONG,
    )
    return result.data, result.latency_ms, result.retries