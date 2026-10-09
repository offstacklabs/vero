from pathlib import Path
import json
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

class RulesUpdateRequest(BaseModel):
    rules: str

class RuleAppendRequest(BaseModel):
    rule: str

class MetricCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    sql: str

class AnnotationRequest(BaseModel):
    annotation: str

@app.get("/api/schemas")
def get_schemas():
    engine = ContextEngine()
    schemas = engine.get_schemas()
    results = [{"table": name, "content": md} for name, md in sorted(schemas.items())]
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

@app.get("/api/rules")
def get_rules():
    engine = ContextEngine()
    return {"rules": engine.get_rules()}

@app.put("/api/rules")
def update_rules(req: RulesUpdateRequest):
    engine = ContextEngine()
    engine.save_rules(req.rules)
    return {"success": True, "rules": engine.get_rules()}

@app.post("/api/rules/append")
def append_rule(req: RuleAppendRequest):
    engine = ContextEngine()
    engine.append_rule(req.rule)
    return {"success": True, "rules": engine.get_rules()}

@app.get("/api/metrics")
def get_metrics():
    engine = ContextEngine()
    return {"metrics": engine.get_metrics()}

@app.post("/api/metrics")
def create_or_update_metric(req: MetricCreateRequest):
    engine = ContextEngine()
    metric_data = {
        "name": req.name.strip(),
        "description": req.description.strip() if req.description else "",
        "sql": req.sql.strip()
    }
    engine.save_metric(metric_data)
    return {"success": True, "metric": metric_data}

@app.delete("/api/metrics/{metric_name}")
def delete_metric(metric_name: str):
    engine = ContextEngine()
    deleted = engine.delete_metric(metric_name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' not found")
    return {"success": True, "deleted": metric_name}

@app.post("/api/schemas/{table_name}/annotate")
def annotate_table(table_name: str, req: AnnotationRequest):
    engine = ContextEngine()
    engine.save_table_annotation(table_name, req.annotation)
    return {"success": True, "table": table_name}

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

from fastapi.responses import StreamingResponse

@app.post("/api/chat")
def chat(req: ChatRequest):
    # Pass config and history? We instantiate a fresh agent for now
    agent = VeroAgent()
    response = agent.ask(req.question, execute=req.execute)
    return response

@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    agent = VeroAgent()
    def event_stream():
        for event in agent.ask_stream(req.question, execute=req.execute):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

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
