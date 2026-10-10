from pathlib import Path
import json
import time
import re
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
    domain: Optional[str] = None

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

@app.get("/api/domains")
def get_domains():
    engine = ContextEngine()
    return {"domains": engine.get_domains()}

class RulesUpdateRequest(BaseModel):
    rules: str
    domain: Optional[str] = "global"

class RuleAppendRequest(BaseModel):
    rule: str
    domain: Optional[str] = "global"

class MetricCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    sql: str
    domain: Optional[str] = "global"

class AnnotationRequest(BaseModel):
    annotation: str

@app.get("/api/schemas")
def get_schemas(domain: Optional[str] = None):
    engine = ContextEngine()
    schemas = engine.get_schemas(domain=domain)
    results = [{"table": name, "content": md} for name, md in sorted(schemas.items())]
    return {"schemas": results, "domain": domain or "all"}

@app.post("/api/sync")
def sync_schemas(domain: str = "global"):
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    try:
        schema_info = db.introspect_schema()
        engine = ContextEngine()
        engine.sync_schemas(schema_info, domain=domain)
        return {"success": True, "tables": len(schema_info), "domain": domain}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rules")
def get_rules(domain: str = "global"):
    engine = ContextEngine()
    return {"rules": engine.get_rules(domain=domain), "domain": domain}

@app.put("/api/rules")
def update_rules(req: RulesUpdateRequest):
    engine = ContextEngine()
    target_domain = req.domain or "global"
    engine.save_rules(req.rules, domain=target_domain)
    return {"success": True, "rules": engine.get_rules(domain=target_domain), "domain": target_domain}

@app.post("/api/rules/append")
def append_rule(req: RuleAppendRequest):
    engine = ContextEngine()
    target_domain = req.domain or "global"
    engine.append_rule(req.rule, domain=target_domain)
    return {"success": True, "rules": engine.get_rules(domain=target_domain), "domain": target_domain}

@app.get("/api/metrics")
def get_metrics(domain: Optional[str] = None):
    engine = ContextEngine()
    return {"metrics": engine.get_metrics(domain=domain), "domain": domain or "all"}

@app.post("/api/metrics")
def create_or_update_metric(req: MetricCreateRequest):
    engine = ContextEngine()
    target_domain = req.domain or "global"
    metric_data = {
        "name": req.name.strip(),
        "description": req.description.strip() if req.description else "",
        "sql": req.sql.strip(),
        "domain": target_domain
    }
    engine.save_metric(metric_data, domain=target_domain)
    return {"success": True, "metric": metric_data}

@app.delete("/api/metrics/{metric_name}")
def delete_metric(metric_name: str, domain: str = "global"):
    engine = ContextEngine()
    deleted = engine.delete_metric(metric_name, domain=domain)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' in domain '{domain}' not found")
    return {"success": True, "deleted": metric_name, "domain": domain}

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
    agent = VeroAgent()
    response = agent.ask(req.question, execute=req.execute, domain=req.domain)
    return response

@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    agent = VeroAgent()
    def event_stream():
        for event in agent.ask_stream(req.question, execute=req.execute, domain=req.domain):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

class SessionCreateRequest(BaseModel):
    title: str
    domain: Optional[str] = "global"

@app.get("/api/sessions")
def list_sessions(domain: Optional[str] = None):
    engine = ContextEngine()
    return {"sessions": engine.get_sessions(domain=domain)}

@app.post("/api/sessions")
def create_session(req: SessionCreateRequest):
    engine = ContextEngine()
    return engine.create_session(title=req.title, domain=req.domain or "global")

@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    engine = ContextEngine()
    return {"messages": engine.get_session_messages(session_id=session_id)}

@app.post("/api/sessions/{session_id}/messages")
def save_session_message(session_id: str, message: Dict[str, Any]):
    engine = ContextEngine()
    engine.save_message(session_id=session_id, message=message)
    return {"success": True}

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    engine = ContextEngine()
    deleted = engine.delete_session(session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "deleted": session_id}

@app.get("/api/history/queries")
def get_query_history(limit: int = 50):
    engine = ContextEngine()
    return {"runs": engine.get_query_runs(limit=limit)}

from fastapi.staticfiles import StaticFiles

@app.post("/api/query")
def run_query(req: QueryRequest):
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    engine = ContextEngine()
    start_time = time.time()
    try:
        data = db.execute_query(req.sql, limit=req.limit or 100)
        duration_ms = round((time.time() - start_time) * 1000, 1)
        row_count = data.get("row_count") or len(data.get("rows", []))
        engine.record_query_run(sql=req.sql, duration_ms=duration_ms, row_count=row_count, error=None)
        return {"success": True, "data": data, "duration_ms": duration_ms}
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 1)
        engine.record_query_run(sql=req.sql, duration_ms=duration_ms, row_count=0, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

# Mount prebuilt Studio UI assets if present
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
