"""Stage 1: Intent Extraction — raw natural language -> structured IntentSchema."""
from app.schemas.models import IntentSchema
from app.pipeline.llm_client import call_structured, MODEL_FAST

SYSTEM_PROMPT = """You are the Intent Extraction stage of a software-generation compiler.
Parse the user's natural language app request into a structured JSON object.

Return a JSON object with exactly these fields:
- "app_name": string (short name for the app)
- "goal": string (one sentence summary of what the app does)
- "entities": array of entity objects, each with "name" (string) and "description" (string)
- "roles": array of plain strings (just the role names, nothing else)
- "features": array of plain strings (short feature descriptions)
- "constraints": array of plain strings (explicit constraints mentioned)
- "assumptions": array of plain strings (assumptions made to fill gaps)
- "ambiguous": boolean (true if prompt is too vague or conflicting)
- "ambiguity_notes": string or null (explain ambiguity if ambiguous is true)

Example output:
{
  "app_name": "CRM",
  "goal": "A customer relationship management system with contacts and analytics.",
  "entities": [
    {"name": "Contact", "description": "A customer or prospect with name and email"},
    {"name": "User", "description": "A person who logs into the system"}
  ],
  "roles": ["admin", "user"],
  "features": ["login", "contact management", "dashboard", "analytics for admins"],
  "constraints": [],
  "assumptions": ["Assumed standard email/password login"],
  "ambiguous": false,
  "ambiguity_notes": null
}

Rules:
- "roles" must be a plain array of strings like ["admin", "user"] NOT objects
- If prompt is vague, set ambiguous=true and fill assumptions with what you assumed
- If prompt has conflicts, set ambiguous=true and explain in ambiguity_notes
"""


def run(user_text: str) -> dict:
    user_prompt = f"User request:\n\"\"\"\n{user_text}\n\"\"\"\n\nExtract the intent from this request and return a JSON object exactly matching the structure shown in the example."
    result = call_structured(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=IntentSchema,
        model=MODEL_FAST,
    )
    return result.data, result.latency_ms, result.retries