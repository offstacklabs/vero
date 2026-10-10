from pathlib import Path
import json
import time
import re
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from vero.agent import VeroAgent
from vero.config import VeroConfig
from vero.context import ContextEngine
from vero.db import DatabaseManager
from vero.auth import AuthManager, User, create_access_token

app = FastAPI(title="Vero Analytics Server", version="0.1.0")

# Enable CORS for Studio UI & client integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
) -> User:
    """
    Validates Bearer JWT token or X-API-Key against centralized database.
    In local OSS mode (default), seamlessly returns the local developer user with zero friction.
    In enterprise OIDC mode, requires valid credentials.
    """
    config = VeroConfig.load()
    mgr = AuthManager()

    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()

    # If valid token provided, authenticate regardless of mode
    if token:
        user = mgr.authenticate(token)
        if user and user.is_active:
            return user
        raise HTTPException(status_code=401, detail="Invalid or expired authentication credentials")

    # In local OSS mode (default), auto-authenticate as local developer
    if not config.auth or config.auth.mode == "local":
        return mgr.get_local_developer_user()

    # In enterprise OIDC mode without credentials, reject with 401
    raise HTTPException(status_code=401, detail="Authentication required: Enterprise SSO or API Key needed")

def require_role(allowed_roles: List[str]):
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access forbidden: User role '{user.role}' lacks required permissions ({', '.join(allowed_roles)})"
            )
        return user
    return role_checker

def check_domain_auth(domain: Optional[str], user: User):
    if not domain or domain == "global":
        return
    mgr = AuthManager()
    if not mgr.can_access_domain(user, domain):
        raise HTTPException(
            status_code=403,
            detail=f"Access forbidden: User '{user.email}' is not authorized to access domain '{domain}'"
        )

@app.get("/api/auth/config")
def get_auth_config():
    """Returns the current authentication mode and IdP provider configuration."""
    config = VeroConfig.load()
    auth_cfg = config.auth if config.auth else None
    oidc_cfg = auth_cfg.oidc if auth_cfg else None
    return {
        "mode": auth_cfg.mode if auth_cfg else "local",
        "provider_name": oidc_cfg.provider_name if oidc_cfg else "Okta",
        "issuer_url": oidc_cfg.issuer_url if oidc_cfg else "",
        "client_id": oidc_cfg.client_id if oidc_cfg else ""
    }

class OIDCLoginRequest(BaseModel):
    email: str
    name: str
    groups: List[str] = []

@app.post("/api/auth/oidc/login")
def oidc_login(req: OIDCLoginRequest):
    """
    Authenticates a user from an enterprise IdP (Okta, OneLogin, Azure AD)
    and dynamically maps their corporate groups to Vero roles and allowed domains.
    """
    mgr = AuthManager()
    user, _ = mgr.map_idp_groups_to_user(
        email=req.email,
        name=req.name,
        groups=req.groups
    )
    token = create_access_token(user)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "allowed_domains": user.allowed_domains
        }
    }

class LoginRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None

@app.post("/api/auth/login")
def login(req: LoginRequest):
    mgr = AuthManager()
    mgr.seed_default_admin()
    user = None
    if req.api_key:
        user = mgr.authenticate(req.api_key)
    elif req.email and req.password:
        user = mgr.authenticate(req.email, req.password)

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials or inactive user account")

    token = create_access_token(user)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "allowed_domains": user.allowed_domains
        }
    }

@app.get("/api/auth/me")
def get_me(user: User = Depends(get_current_user)):
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "allowed_domains": user.allowed_domains
        }
    }

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
def get_domains(user: User = Depends(get_current_user)):
    engine = ContextEngine()
    all_domains = engine.get_domains()
    mgr = AuthManager()
    accessible = [d for d in all_domains if mgr.can_access_domain(user, d["id"])]
    return {"domains": accessible}

class DomainCreateRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""

@app.post("/api/domains")
def create_domain(req: DomainCreateRequest, user: User = Depends(require_role(["admin"]))):
    engine = ContextEngine()
    created = engine.create_domain(domain_id=req.id, name=req.name, description=req.description or "")
    return {"success": True, "domain": created}

class UserCreateRequest(BaseModel):
    email: str
    name: str
    password: Optional[str] = None
    role: str = "analyst"
    allowed_domains: Optional[List[str]] = None

@app.get("/api/users")
def list_users(user: User = Depends(require_role(["admin"]))):
    mgr = AuthManager()
    users = mgr.get_all_users()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "allowed_domains": u.allowed_domains,
                "is_active": u.is_active
            }
            for u in users
        ]
    }

@app.post("/api/users")
def create_user(req: UserCreateRequest, user: User = Depends(require_role(["admin"]))):
    mgr = AuthManager()
    new_user, raw_api_key = mgr.create_user(
        email=req.email,
        name=req.name,
        password=req.password,
        role=req.role.lower().strip(),
        allowed_domains=req.allowed_domains or ["*"]
    )
    return {
        "success": True,
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "role": new_user.role,
            "allowed_domains": new_user.allowed_domains,
            "is_active": new_user.is_active
        },
        "api_key": raw_api_key
    }

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str, user: User = Depends(require_role(["admin"]))):
    mgr = AuthManager()
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own user account")
    deleted = mgr.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "deleted": user_id}

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
def update_rules(req: RulesUpdateRequest, user: User = Depends(require_role(["admin"]))):
    target_domain = req.domain or "global"
    check_domain_auth(target_domain, user)
    engine = ContextEngine()
    engine.save_rules(req.rules, domain=target_domain)
    return {"success": True, "rules": engine.get_rules(domain=target_domain), "domain": target_domain}

@app.post("/api/rules/append")
def append_rule(req: RuleAppendRequest, user: User = Depends(require_role(["admin"]))):
    target_domain = req.domain or "global"
    check_domain_auth(target_domain, user)
    engine = ContextEngine()
    engine.append_rule(req.rule, domain=target_domain)
    return {"success": True, "rules": engine.get_rules(domain=target_domain), "domain": target_domain}

@app.get("/api/metrics")
def get_metrics(domain: Optional[str] = None):
    engine = ContextEngine()
    return {"metrics": engine.get_metrics(domain=domain), "domain": domain or "all"}

@app.post("/api/metrics")
def create_or_update_metric(req: MetricCreateRequest, user: User = Depends(require_role(["admin"]))):
    target_domain = req.domain or "global"
    check_domain_auth(target_domain, user)
    engine = ContextEngine()
    metric_data = {
        "name": req.name.strip(),
        "description": req.description.strip() if req.description else "",
        "sql": req.sql.strip(),
        "domain": target_domain
    }
    engine.save_metric(metric_data, domain=target_domain)
    return {"success": True, "metric": metric_data}

@app.delete("/api/metrics/{metric_name}")
def delete_metric(metric_name: str, domain: str = "global", user: User = Depends(require_role(["admin"]))):
    check_domain_auth(domain, user)
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
def chat(req: ChatRequest, user: User = Depends(get_current_user)):
    check_domain_auth(req.domain, user)
    agent = VeroAgent()
    response = agent.ask(req.question, execute=req.execute, domain=req.domain)
    return response

@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest, user: User = Depends(get_current_user)):
    check_domain_auth(req.domain, user)
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

class TilePinRequest(BaseModel):
    title: str
    tile_type: str = "chart"  # kpi, chart, table
    chart_type: Optional[str] = "bar"
    sql: Optional[str] = ""
    data: Optional[Dict[str, Any]] = None
    domain: Optional[str] = "global"

@app.get("/api/dashboard/tiles")
def get_dashboard_tiles(domain: Optional[str] = None):
    engine = ContextEngine()
    return {"tiles": engine.get_dashboard_tiles(domain=domain)}

@app.post("/api/dashboard/tiles")
def pin_dashboard_tile(req: TilePinRequest):
    engine = ContextEngine()
    tile = req.model_dump()
    pinned = engine.pin_tile(tile, domain=req.domain or "global")
    return {"success": True, "tile": pinned}

@app.delete("/api/dashboard/tiles/{tile_id}")
def unpin_dashboard_tile(tile_id: str):
    engine = ContextEngine()
    unpinned = engine.unpin_tile(tile_id)
    if not unpinned:
        raise HTTPException(status_code=404, detail="Dashboard tile not found")
    return {"success": True, "unpinned": tile_id}

class EstimateRequest(BaseModel):
    sql: str

@app.post("/api/query/estimate")
def estimate_query(req: EstimateRequest):
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    res = db.estimate_query_cost(req.sql)
    return res

from fastapi.staticfiles import StaticFiles

@app.post("/api/query")
def run_query(req: QueryRequest, user: User = Depends(require_role(["admin", "analyst"]))):
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    engine = ContextEngine()
    start_time = time.time()
    try:
        data = db.execute_query(req.sql, limit=req.limit or 100, enforce_cost_guard=True)
        duration_ms = round((time.time() - start_time) * 1000, 1)
        row_count = data.get("row_count") or len(data.get("rows", []))
        bytes_scanned = data.get("bytes_scanned", 0)
        cost_usd = data.get("cost_usd", 0.0)
        engine.record_query_run(
            sql=req.sql,
            duration_ms=duration_ms,
            row_count=row_count,
            error=None,
            bytes_scanned=bytes_scanned,
            cost_usd=cost_usd
        )
        return {"success": True, "data": data, "duration_ms": duration_ms}
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 1)
        engine.record_query_run(sql=req.sql, duration_ms=duration_ms, row_count=0, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/observability/stats")
def get_observability_stats():
    """Aggregates end-to-end token consumption, LLM spend, warehouse compute costs, and Cost Guard metrics."""
    config = VeroConfig.load()
    engine = ContextEngine()
    runs = engine.get_query_runs(limit=500)
    sessions = engine.get_sessions()

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_llm_spend = 0.0

    daily_costs: Dict[str, Dict[str, float]] = {}

    for s in sessions:
        msgs = engine.get_session_messages(s["id"])
        for m in msgs:
            tel = m.get("telemetry") or {}
            p_tok = tel.get("prompt_tokens", 0)
            c_tok = tel.get("completion_tokens", 0)
            llm_cost = tel.get("llm_cost_usd", 0.0)
            total_prompt_tokens += p_tok
            total_completion_tokens += c_tok
            total_llm_spend += llm_cost

            # Group daily
            date_str = str(m.get("created_at") or "")[:10]
            if date_str and len(date_str) == 10:
                if date_str not in daily_costs:
                    daily_costs[date_str] = {"llm_cost": 0.0, "warehouse_cost": 0.0, "query_count": 0}
                daily_costs[date_str]["llm_cost"] += llm_cost

    total_queries = len(runs)
    total_warehouse_spend = 0.0
    cost_guard_savings = 0.0
    total_latency_ms = 0.0

    for r in runs:
        w_cost = r.get("cost_usd", 0.0) or 0.0
        total_warehouse_spend += w_cost
        total_latency_ms += (r.get("duration_ms", 0.0) or 0.0)

        # Check for Cost Guard blocked runs
        err = r.get("error", "") or ""
        if "cost guard blocked" in err.lower():
            # Estimate savings from prevented runaway scan
            b_scanned = r.get("bytes_scanned", 0) or (15 * 1024 * 1024 * 1024)
            cost_guard_savings += round((b_scanned / (1024 ** 4)) * (config.cost_guard.rates.bigquery_per_tb_usd if config.cost_guard else 6.25), 4)

        date_str = str(r.get("executed_at") or "")[:10]
        if date_str and len(date_str) == 10:
            if date_str not in daily_costs:
                daily_costs[date_str] = {"llm_cost": 0.0, "warehouse_cost": 0.0, "query_count": 0}
            daily_costs[date_str]["warehouse_cost"] += w_cost
            daily_costs[date_str]["query_count"] += 1

    avg_latency = round(total_latency_ms / max(total_queries, 1), 1)
    top_queries = sorted(runs, key=lambda x: (x.get("cost_usd", 0.0) or 0.0, x.get("duration_ms", 0.0) or 0.0), reverse=True)[:5]

    daily_breakdown = [
        {
            "date": d,
            "llm_cost": round(v["llm_cost"], 4),
            "warehouse_cost": round(v["warehouse_cost"], 4),
            "total_cost": round(v["llm_cost"] + v["warehouse_cost"], 4),
            "query_count": int(v["query_count"])
        }
        for d, v in sorted(daily_costs.items())
    ]

    return {
        "total_queries": total_queries,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "llm_spend_usd": round(total_llm_spend, 4),
        "warehouse_spend_usd": round(total_warehouse_spend, 4),
        "total_spend_usd": round(total_llm_spend + total_warehouse_spend, 4),
        "cost_guard_savings_usd": round(cost_guard_savings, 4),
        "avg_latency_ms": avg_latency,
        "active_dialect": config.database.dialect,
        "rates": config.cost_guard.rates.model_dump() if config.cost_guard else {},
        "top_expensive_queries": top_queries,
        "daily_breakdown": daily_breakdown
    }

# Mount prebuilt Studio UI assets if present
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
