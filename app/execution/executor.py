"""
Execution Awareness layer.
Takes a validated AppConfig and proves it's directly usable by:
  1. Actually creating a SQLite database from the DB schema (real CREATE TABLE statements run).
  2. Generating real FastAPI route stub files from the API schema (syntactically valid Python,
     importable).
  3. Generating a minimal JSON-driven HTML page from the UI schema.
No manual fixes required -- if this script fails, the config is considered broken.
"""
import os
import sqlite3
import json

SQL_TYPE_MAP = {
    "TEXT": "TEXT",
    "INTEGER": "INTEGER",
    "REAL": "REAL",
    "BOOLEAN": "INTEGER",  # SQLite has no native boolean
    "DATE": "TEXT",
    "FOREIGN_KEY": "INTEGER",
}


def build_database(db_schema: dict, out_path: str) -> str:
    if os.path.exists(out_path):
        os.remove(out_path)
    conn = sqlite3.connect(out_path)
    cur = conn.cursor()
    for table in db_schema["tables"]:
        # Filter out any 'id' column the model generated since we add it automatically
        table_columns = [c for c in table["columns"] if c["name"].lower() != "id"]
        cols_sql = ['id INTEGER PRIMARY KEY AUTOINCREMENT']
        fks_sql = []
        for col in table_columns:
            sql_type = SQL_TYPE_MAP[col["type"]]
            nullable = "" if col.get("nullable") else " NOT NULL"
            cols_sql.append(f'"{col["name"]}" {sql_type}{nullable}')
            if col["type"] == "FOREIGN_KEY" and col.get("foreign_key_table"):
                fks_sql.append(
                    f'FOREIGN KEY ("{col["name"]}") REFERENCES "{col["foreign_key_table"]}"(id)'
                )
        all_defs = cols_sql + fks_sql
        create_stmt = f'CREATE TABLE "{table["name"]}" ({", ".join(all_defs)});'
        cur.execute(create_stmt)
    conn.commit()
    conn.close()
    return out_path


def generate_api_routes(api_schema: dict, out_path: str) -> str:
    lines = [
        "from fastapi import APIRouter",
        "",
        "router = APIRouter()",
        "",
    ]
    method_to_decorator = {
        "GET": "get", "POST": "post", "PUT": "put", "PATCH": "patch", "DELETE": "delete"
    }
    for ep in api_schema["endpoints"]:
        decorator = method_to_decorator[ep["method"]]
        func_name = ep["id"].replace("-", "_")
        lines.append(f'@router.{decorator}("{ep["path"]}")')
        lines.append(f"def {func_name}():")
        lines.append(f'    """Auto-generated stub for entity: {ep["entity"]}. Roles allowed: {ep["roles_allowed"]}"""')
        lines.append(f"    return {{'endpoint': '{ep['id']}', 'entity': '{ep['entity']}'}}")
        lines.append("")
    code = "\n".join(lines)
    with open(out_path, "w") as f:
        f.write(code)
    # Syntax-check the generated file
    compile(code, out_path, "exec")
    return out_path


def generate_ui_preview(ui_schema: dict, out_path: str) -> str:
    parts = ["<html><body style='font-family:sans-serif'>"]
    for page in ui_schema["pages"]:
        parts.append(f"<h2>{page['name']} ({page['route']})</h2>")
        parts.append(f"<p>Roles allowed: {', '.join(page['roles_allowed'])}</p>")
        parts.append("<ul>")
        for comp in page["components"]:
            parts.append(f"<li>[{comp['type']}] {comp['label']}</li>")
        parts.append("</ul><hr/>")
    parts.append("</body></html>")
    html = "\n".join(parts)
    with open(out_path, "w") as f:
        f.write(html)
    return out_path


def execute_config(config: dict, out_dir: str) -> dict:
    """Runs all three execution checks and returns a report. Raises if any fails."""
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    db_path = build_database(config["db"], os.path.join(out_dir, "app.db"))
    report["db"] = {"status": "ok", "path": db_path, "tables_created": len(config["db"]["tables"])}

    routes_path = generate_api_routes(config["api"], os.path.join(out_dir, "routes.py"))
    report["api"] = {"status": "ok", "path": routes_path, "endpoints_generated": len(config["api"]["endpoints"])}

    ui_path = generate_ui_preview(config["ui"], os.path.join(out_dir, "preview.html"))
    report["ui"] = {"status": "ok", "path": ui_path, "pages_generated": len(config["ui"]["pages"])}

    return report
