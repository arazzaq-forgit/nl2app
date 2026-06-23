"""
Stage 3: Schema Generation.
Split into 4 independent sub-stages (UI, API, DB, Auth) so each can be validated and
repaired in isolation -- this is what makes the pipeline modular rather than a single
monolithic "generate everything" call.
Prompts use concrete examples rather than raw JSON schema definitions, which works
much better with smaller/faster models like llama-3.1-8b-instant.
"""
import json
from app.schemas.models import UISchema, APISchema, DBSchema, AuthSchema
from app.pipeline.llm_client import call_structured, MODEL_STRONG

UI_SYSTEM = """You generate a UI schema for a web application.
Return a JSON object with a single key "pages" containing an array of page objects.
Each page object must have exactly these fields:
- "name": string (page name)
- "route": string (URL path like "/contacts")
- "roles_allowed": array of role name strings
- "components": array of component objects

Each component object must have exactly these fields:
- "type": one of: "text", "input", "button", "table", "form", "chart", "card", "nav"
- "label": string (display label)
- "bound_field": string or null (format: "EntityName.fieldname")
- "api_call": string or null (endpoint id like "list_contacts")

Example output:
{
  "pages": [
    {
      "name": "ContactList",
      "route": "/contacts",
      "roles_allowed": ["admin", "user"],
      "components": [
        {"type": "table", "label": "Contacts", "bound_field": "Contact.name", "api_call": "list_contacts"},
        {"type": "button", "label": "Add Contact", "bound_field": null, "api_call": "create_contact"}
      ]
    }
  ]
}"""

API_SYSTEM = """You generate a REST API schema for a web application.
Return a JSON object with a single key "endpoints" containing an array of endpoint objects.
Each endpoint object must have exactly these fields:
- "id": string (unique snake_case identifier like "list_contacts")
- "path": string (URL path like "/contacts")
- "method": one of: "GET", "POST", "PUT", "PATCH", "DELETE"
- "entity": string (DB table name this endpoint operates on)
- "request_fields": array of field objects (can be empty array)
- "response_fields": array of field objects (can be empty array)
- "roles_allowed": array of role name strings

Each field object must have exactly these fields:
- "name": string
- "type": string (like "string", "number", "boolean")
- "required": boolean

IMPORTANT: Generate a MAXIMUM of 6 endpoints total. Focus on the most essential ones only (list, create, login). Do NOT generate update/delete endpoints unless absolutely critical.

Example output:
{
  "endpoints": [
    {
      "id": "list_contacts",
      "path": "/contacts",
      "method": "GET",
      "entity": "Contact",
      "request_fields": [],
      "response_fields": [
        {"name": "name", "type": "string", "required": true},
        {"name": "email", "type": "string", "required": true}
      ],
      "roles_allowed": ["admin", "user"]
    },
    {
      "id": "create_contact",
      "path": "/contacts",
      "method": "POST",
      "entity": "Contact",
      "request_fields": [
        {"name": "name", "type": "string", "required": true},
        {"name": "email", "type": "string", "required": true}
      ],
      "response_fields": [
        {"name": "id", "type": "number", "required": true}
      ],
      "roles_allowed": ["admin"]
    }
  ]
}"""

DB_SYSTEM = """You generate a database schema for a web application using SQLite-compatible types.
Return a JSON object with a single key "tables" containing an array of table objects.
Each table object must have exactly these fields:
- "name": string (table name, matches entity name)
- "columns": array of column objects

Each column object must have exactly these fields:
- "name": string (column name)
- "type": one of: "TEXT", "INTEGER", "REAL", "BOOLEAN", "DATE", "FOREIGN_KEY"
- "foreign_key_table": string or null (only set when type is "FOREIGN_KEY")
- "nullable": boolean

Example output:
{
  "tables": [
    {
      "name": "User",
      "columns": [
        {"name": "username", "type": "TEXT", "foreign_key_table": null, "nullable": false},
        {"name": "email", "type": "TEXT", "foreign_key_table": null, "nullable": false},
        {"name": "role", "type": "TEXT", "foreign_key_table": null, "nullable": false}
      ]
    },
    {
      "name": "Contact",
      "columns": [
        {"name": "name", "type": "TEXT", "foreign_key_table": null, "nullable": false},
        {"name": "email", "type": "TEXT", "foreign_key_table": null, "nullable": false},
        {"name": "owner_id", "type": "FOREIGN_KEY", "foreign_key_table": "User", "nullable": false}
      ]
    }
  ]
}"""

AUTH_SYSTEM = """You generate an auth schema for a web application.
Return a JSON object with exactly these two keys:
- "roles": array of role objects
- "default_role": string (the role new users get by default)

Each role object must have exactly these fields:
- "name": string (role name like "admin", "user", "premium_user")
- "permissions": array of permission name strings
- "is_premium_gated": boolean (true if this role requires payment)

Example output:
{
  "roles": [
    {
      "name": "user",
      "permissions": ["view_dashboard", "create_contact"],
      "is_premium_gated": false
    },
    {
      "name": "premium_user",
      "permissions": ["view_dashboard", "create_contact", "export_data"],
      "is_premium_gated": true
    },
    {
      "name": "admin",
      "permissions": ["view_dashboard", "create_contact", "view_analytics", "manage_users"],
      "is_premium_gated": false
    }
  ],
  "default_role": "user"
}"""


def _run(system_prompt, architecture, schema, label):
    # Send only entity names and fields, not the full architecture JSON
    # This keeps the prompt short enough for the 8B model to handle reliably
    entities_simple = [
        {
            "name": e["name"],
            "fields": [{"name": f["name"], "type": f["type"], "relation_target": f.get("relation_target")} for f in e["fields"]]
        }
        for e in architecture.get("entities", [])
    ]
    roles_simple = [r["role"] for r in architecture.get("roles", [])]

    user_prompt = (
        f"Entities: {json.dumps(entities_simple)}\n"
        f"Roles: {json.dumps(roles_simple)}\n\n"
        f"Generate the {label} schema. Return only a JSON object matching the structure shown in the example."
    )
    result = call_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=schema,
        model=MODEL_STRONG
    )
    return result.data, result.latency_ms, result.retries


def run_ui(architecture: dict) -> dict:
    return _run(UI_SYSTEM, architecture, UISchema, "UI")


def run_api(architecture: dict) -> dict:
    return _run(API_SYSTEM, architecture, APISchema, "API")


def run_db(architecture: dict) -> dict:
    return _run(DB_SYSTEM, architecture, DBSchema, "database")


def run_auth(architecture: dict) -> dict:
    return _run(AUTH_SYSTEM, architecture, AuthSchema, "auth")