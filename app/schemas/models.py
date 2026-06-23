"""
Core schema definitions for the NL -> App Config compiler pipeline.
Every stage of the pipeline produces output that MUST validate against one of these models.
This is the "strict contract" required by the spec.
"""
from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# STAGE 1: Intent Extraction
# ---------------------------------------------------------------------------

class IntentEntity(BaseModel):
    name: str
    description: str


class IntentSchema(BaseModel):
    app_name: str
    goal: str = Field(..., description="One sentence summary of what the app does")
    entities: List[IntentEntity] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list, description="Explicit constraints the user mentioned")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made to fill gaps in a vague prompt")
    ambiguous: bool = Field(False, description="True if the prompt was too vague/conflicting to resolve confidently")
    ambiguity_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# STAGE 2: System Design Layer
# ---------------------------------------------------------------------------

class ArchitectureField(BaseModel):
    name: str
    type: Literal["string", "number", "boolean", "date", "enum", "relation"]
    required: bool = True
    enum_values: Optional[List[str]] = None
    relation_target: Optional[str] = Field(None, description="Entity name this field relates to, if type=relation")


class ArchitectureEntity(BaseModel):
    name: str
    fields: List[ArchitectureField]


class RolePermission(BaseModel):
    role: str
    can_access: List[str] = Field(default_factory=list, description="Entity or feature names this role can access")


class ArchitectureSchema(BaseModel):
    entities: List[ArchitectureEntity]
    roles: List[RolePermission]
    flows: List[str] = Field(default_factory=list, description="Key user flows, e.g. 'signup -> verify email -> dashboard'")


# ---------------------------------------------------------------------------
# STAGE 3a: UI Schema
# ---------------------------------------------------------------------------

class UIComponent(BaseModel):
    type: Literal["text", "input", "button", "table", "form", "chart", "card", "nav", "select", "checkbox", "dropdown", "modal", "list"]
    label: str = "Component"
    bound_field: Optional[str] = Field(None, description="entity.field this component is bound to, if any")
    api_call: Optional[str] = Field(None, description="endpoint id this component triggers, if any")


class UIPage(BaseModel):
    name: str
    route: str
    roles_allowed: List[str]
    components: List[UIComponent]


class UISchema(BaseModel):
    pages: List[UIPage]


# ---------------------------------------------------------------------------
# STAGE 3b: API Schema
# ---------------------------------------------------------------------------

class APIField(BaseModel):
    name: str
    type: str
    required: bool = True


class APIEndpoint(BaseModel):
    id: str
    path: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    entity: str = Field(default="Unknown", description="DB entity this endpoint operates on")
    request_fields: List[APIField] = Field(default_factory=list)
    response_fields: List[APIField] = Field(default_factory=list)
    roles_allowed: List[str] = Field(default_factory=list)


class APISchema(BaseModel):
    endpoints: List[APIEndpoint]


# ---------------------------------------------------------------------------
# STAGE 3c: DB Schema
# ---------------------------------------------------------------------------

class DBColumn(BaseModel):
    name: str
    type: Literal["TEXT", "INTEGER", "REAL", "BOOLEAN", "DATE", "FOREIGN_KEY"]
    foreign_key_table: Optional[str] = None
    nullable: bool = False


class DBTable(BaseModel):
    name: str
    columns: List[DBColumn]


class DBSchema(BaseModel):
    tables: List[DBTable]


# ---------------------------------------------------------------------------
# STAGE 3d: Auth Schema
# ---------------------------------------------------------------------------

class AuthRole(BaseModel):
    name: str
    permissions: List[str]
    is_premium_gated: bool = False


class AuthSchema(BaseModel):
    roles: List[AuthRole]
    default_role: str


# ---------------------------------------------------------------------------
# Combined output
# ---------------------------------------------------------------------------

class RepairLogEntry(BaseModel):
    stage: str
    issue: str
    action: Literal["auto_repaired", "regenerated", "unresolved"]


class AppConfig(BaseModel):
    intent: IntentSchema
    architecture: ArchitectureSchema
    ui: UISchema
    api: APISchema
    db: DBSchema
    auth: AuthSchema
    repair_log: List[RepairLogEntry] = Field(default_factory=list)
    stage_latencies_ms: dict = Field(default_factory=dict)
