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

@app.get("/api/rules")
def get_rules():
    engine = ContextEngine()
    if engine.rules_file.exists():
        return {"rules": engine.rules_file.read_text(encoding="utf-8")}
    return {"rules": ""}

@app.post("/api/chat")
def chat(req: ChatRequest):
    # Pass config and history? We instantiate a fresh agent for now
    agent = VeroAgent()
    response = agent.ask(req.question, execute=req.execute)
    return response

@app.post("/api/query")
def run_query(req: QueryRequest):
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    try:
        data = db.execute_query(req.sql, limit=req.limit or 100)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
