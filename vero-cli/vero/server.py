from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from vero.agent import VeroAgent
from vero.config import VeroConfig
from vero.context import ContextEngine
from vero.db import DatabaseManager

app = FastAPI(title="Vero Analytics Server", version="0.1.0")

# Enable CORS for local Studio UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str
    execute: bool = True

class QueryRequest(BaseModel):
    sql: str
    limit: Optional[int] = 100

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "vero"}

@app.get("/api/config")
def get_config():
    config = VeroConfig.load()
    return config.model_dump()

@app.get("/api/schemas")
def get_schemas():
    engine = ContextEngine()
    schemas_dir = engine.schemas_dir
    if not schemas_dir.exists():
        return {"schemas": []}
    
    results = []
    for file in sorted(schemas_dir.glob("*.md")):
        if file.name != "README.md":
            results.append({
                "table": file.stem,
                "content": file.read_text(encoding="utf-8")
            })
    return {"schemas": results}

@app.post("/api/sync")
def sync_schemas():
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    try:
        schema_info = db.introspect_schema()
        engine = ContextEngine()
        engine.sync_schemas(schema_info)
        return {"success": True, "tables": len(schema_info)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import yaml
import time
import re

@app.get("/api/rules")
def get_rules():
    engine = ContextEngine()
    if engine.rules_file.exists():
        return {"rules": engine.rules_file.read_text(encoding="utf-8")}
    return {"rules": ""}

@app.get("/api/metrics")
def get_metrics():
    engine = ContextEngine()
    if engine.metrics_file.exists():
        try:
            with open(engine.metrics_file, 'r', encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return {"metrics": data.get("metrics", [])}
        except Exception:
            return {"metrics": []}
    return {"metrics": []}

@app.get("/api/tables/{table_name}/preview")
def preview_table(table_name: str):
    """Fetches a quick 10-row sample for any warehouse table."""
    if not re.match(r"^[a-zA-Z0-9_\.]+$", table_name):
        raise HTTPException(status_code=400, detail="Invalid table identifier")
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    sql = f"SELECT * FROM {table_name} LIMIT 10"
    start_time = time.time()
    try:
        data = db.execute_query(sql, limit=10)
        duration_ms = round((time.time() - start_time) * 1000, 1)
        return {
            "table": table_name,
            "sql": sql,
            "data": data,
            "duration_ms": duration_ms
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chat")
def chat(req: ChatRequest):
    # Pass config and history? We instantiate a fresh agent for now
    agent = VeroAgent()
    response = agent.ask(req.question, execute=req.execute)
    return response

from fastapi.staticfiles import StaticFiles

@app.post("/api/query")
def run_query(req: QueryRequest):
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    start_time = time.time()
    try:
        data = db.execute_query(req.sql, limit=req.limit or 100)
        duration_ms = round((time.time() - start_time) * 1000, 1)
        return {"success": True, "data": data, "duration_ms": duration_ms}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Mount prebuilt Studio UI assets if present
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
