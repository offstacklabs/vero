from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import uuid
import yaml
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, text, Table, Column, String, Text, MetaData, Integer, Float, DateTime
)

class ContextStorage(ABC):
    """Abstract interface for pluggable multi-domain context persistence."""

    @abstractmethod
    def get_domains(self) -> List[Dict[str, str]]:
        """Returns registered domain namespaces (e.g. global, finance, marketing)."""
        pass

    @abstractmethod
    def get_rules(self, domain: str = "global") -> str:
        """Returns business rules. If domain != 'global', inherits global rules."""
        pass

    @abstractmethod
    def save_rules(self, rules: str, domain: str = "global") -> None:
        """Overwrites business rules for a specific domain."""
        pass

    @abstractmethod
    def append_rule(self, rule: str, domain: str = "global") -> None:
        """Appends a new business rule to a domain."""
        pass

    @abstractmethod
    def get_metrics(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns semantic metrics. If domain is set, includes global + domain metrics."""
        pass

    @abstractmethod
    def save_metric(self, metric: Dict[str, Any], domain: str = "global") -> None:
        """Creates or updates a semantic metric within a domain."""
        pass

    @abstractmethod
    def delete_metric(self, name: str, domain: str = "global") -> bool:
        """Deletes a metric by name and domain."""
        pass

    @abstractmethod
    def get_schemas(self, domain: Optional[str] = None) -> Dict[str, str]:
        """Returns table schemas as {table_name: schema_markdown}, optionally filtered by domain."""
        pass

    @abstractmethod
    def save_schema(self, table_name: str, schema_md: str, domain: str = "global") -> None:
        """Saves a table schema markdown partitioned by domain."""
        pass

    @abstractmethod
    def delete_schema(self, table_name: str) -> bool:
        """Deletes a table schema."""
        pass

    @abstractmethod
    def save_table_annotation(self, table_name: str, annotation: str) -> None:
        """Attaches custom business notes/annotations to a table."""
        pass

    # --- Session & History Persistence ---
    @abstractmethod
    def get_sessions(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns past chat sessions."""
        pass

    @abstractmethod
    def create_session(self, title: str, domain: str = "global") -> Dict[str, Any]:
        """Creates a new chat session."""
        pass

    @abstractmethod
    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns all messages for a session."""
        pass

    @abstractmethod
    def save_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """Saves a message to a session."""
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Deletes a chat session and its messages."""
        pass

    @abstractmethod
    def record_query_run(self, sql: str, duration_ms: float, row_count: int, error: Optional[str] = None) -> None:
        """Logs a query execution in the history."""
        pass

    @abstractmethod
    def get_query_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent query runs."""
        pass

    # --- Pinned Dashboard Tiles ---
    @abstractmethod
    def get_dashboard_tiles(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns pinned dashboard tiles, optionally filtered by domain."""
        pass

    @abstractmethod
    def pin_tile(self, tile: Dict[str, Any], domain: str = "global") -> Dict[str, Any]:
        """Pins a KPI card, chart, or table to the dashboard."""
        pass

    @abstractmethod
    def unpin_tile(self, tile_id: str) -> bool:
        """Removes a pinned tile from the dashboard."""
        pass


class LocalContextStorage(ContextStorage):
    """File-based context storage with multi-domain partitioning support."""

    def __init__(self, context_dir: Path):
        self.context_dir = context_dir
        self.schemas_dir = self.context_dir / "schemas"
        self.metrics_file = self.context_dir / "metrics.yaml"
        self.rules_file = self.context_dir / "RULES.md"
        self.domains_dir = self.context_dir / "domains"
        self.history_dir = self.context_dir / "history"
        self.sessions_file = self.history_dir / "sessions.json"
        self.query_runs_file = self.history_dir / "query_runs.json"
        self.tiles_file = self.history_dir / "dashboard_tiles.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.schemas_dir.mkdir(parents=True, exist_ok=True)
        self.domains_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def get_domains(self) -> List[Dict[str, str]]:
        domains = [
            {"id": "global", "name": "Global (Shared)", "description": "Enterprise-wide rules and definitions"}
        ]
        if self.domains_dir.exists():
            for d in sorted(self.domains_dir.iterdir()):
                if d.is_dir():
                    domains.append({
                        "id": d.name,
                        "name": d.name.capitalize(),
                        "description": f"{d.name.capitalize()} business domain"
                    })
        return domains

    def _get_domain_rules_file(self, domain: str) -> Path:
        if domain == "global":
            return self.rules_file
        domain_folder = self.domains_dir / domain
        domain_folder.mkdir(parents=True, exist_ok=True)
        return domain_folder / "RULES.md"

    def get_rules(self, domain: str = "global") -> str:
        global_rules = self.rules_file.read_text(encoding="utf-8") if self.rules_file.exists() else ""
        if domain == "global":
            return global_rules
        
        domain_file = self._get_domain_rules_file(domain)
        domain_rules = domain_file.read_text(encoding="utf-8") if domain_file.exists() else ""
        
        parts = []
        if global_rules.strip():
            parts.append(global_rules.strip())
        if domain_rules.strip():
            parts.append(f"\n## [{domain.capitalize()} Domain Rules]\n{domain_rules.strip()}")
        return "\n".join(parts)

    def save_rules(self, rules: str, domain: str = "global") -> None:
        target_file = self._get_domain_rules_file(domain)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(rules.strip() + "\n", encoding="utf-8")

    def append_rule(self, rule: str, domain: str = "global") -> None:
        target_file = self._get_domain_rules_file(domain)
        current = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
        clean_rule = rule.strip()
        if not clean_rule.startswith("- "):
            clean_rule = f"- {clean_rule}"
        header = f"# {domain.capitalize()} Analytics Rules\n\n" if not current.strip() else ""
        new_rules = f"{current.rstrip()}\n{clean_rule}\n" if current.strip() else f"{header}{clean_rule}\n"
        self.save_rules(new_rules, domain=domain)

    def get_metrics(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    raw_metrics = data.get("metrics", [])
                    for m in raw_metrics:
                        if "domain" not in m:
                            m["domain"] = "global"
                        metrics.append(m)
            except Exception:
                pass

        if not domain:
            return metrics
        return [m for m in metrics if m.get("domain") in ["global", domain]]

    def save_metric(self, metric: Dict[str, Any], domain: str = "global") -> None:
        self._ensure_dirs()
        metrics = self.get_metrics(domain=None)
        metric_to_save = dict(metric)
        metric_to_save["domain"] = metric.get("domain", domain)

        updated = False
        for i, m in enumerate(metrics):
            if m.get("name") == metric_to_save["name"] and m.get("domain") == metric_to_save["domain"]:
                metrics[i] = metric_to_save
                updated = True
                break
        if not updated:
            metrics.append(metric_to_save)

        with open(self.metrics_file, "w", encoding="utf-8") as f:
            yaml.dump({"metrics": metrics}, f, default_flow_style=False, sort_keys=False)

    def delete_metric(self, name: str, domain: str = "global") -> bool:
        metrics = self.get_metrics(domain=None)
        filtered = [
            m for m in metrics 
            if not (m.get("name") == name and m.get("domain", "global") == domain)
        ]
        if len(filtered) < len(metrics):
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                yaml.dump({"metrics": filtered}, f, default_flow_style=False, sort_keys=False)
            return True
        return False

    def get_schemas(self, domain: Optional[str] = None) -> Dict[str, str]:
        results = {}
        if self.schemas_dir.exists():
            for p in sorted(self.schemas_dir.glob("*.md")):
                if p.name != "README.md":
                    content = p.read_text(encoding="utf-8")
                    table_domain = "global"
                    for line in content.split("\n")[:5]:
                        if line.startswith("<!-- domain:"):
                            table_domain = line.replace("<!-- domain:", "").replace("-->", "").strip()
                            break
                    
                    if domain is None or domain == "global" or table_domain in ["global", domain]:
                        results[p.stem] = content
        return results

    def save_schema(self, table_name: str, schema_md: str, domain: str = "global") -> None:
        self._ensure_dirs()
        file_path = self.schemas_dir / f"{table_name}.md"
        content = f"<!-- domain: {domain} -->\n{schema_md.strip()}\n"
        file_path.write_text(content, encoding="utf-8")

    def delete_schema(self, table_name: str) -> bool:
        file_path = self.schemas_dir / f"{table_name}.md"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def save_table_annotation(self, table_name: str, annotation: str) -> None:
        self._ensure_dirs()
        file_path = self.schemas_dir / f"{table_name}.md"
        current_md = file_path.read_text(encoding="utf-8") if file_path.exists() else f"# Table: `{table_name}`\n"
        
        annotation_block = f"\n\n## Business Notes & Annotations\n{annotation.strip()}\n"
        if "## Business Notes & Annotations" in current_md:
            parts = current_md.split("## Business Notes & Annotations")
            new_md = parts[0].rstrip() + annotation_block
        else:
            new_md = current_md.rstrip() + annotation_block
            
        file_path.write_text(new_md, encoding="utf-8")

    # --- Session & History (Local JSON) ---
    def _load_sessions_data(self) -> Dict[str, Any]:
        if self.sessions_file.exists():
            try:
                return json.loads(self.sessions_file.read_text(encoding="utf-8"))
            except Exception:
                return {"sessions": [], "messages": {}}
        return {"sessions": [], "messages": {}}

    def _save_sessions_data(self, data: Dict[str, Any]) -> None:
        self._ensure_dirs()
        self.sessions_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_sessions(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._load_sessions_data()
        sessions = data.get("sessions", [])
        if domain and domain != "global":
            return [s for s in sessions if s.get("domain") in ["global", domain]]
        return sessions

    def create_session(self, title: str, domain: str = "global") -> Dict[str, Any]:
        data = self._load_sessions_data()
        sess_id = str(uuid.uuid4())[:8]
        new_sess = {
            "id": sess_id,
            "title": title,
            "domain": domain,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        data.setdefault("sessions", []).insert(0, new_sess)
        data.setdefault("messages", {})[sess_id] = []
        self._save_sessions_data(data)
        return new_sess

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        data = self._load_sessions_data()
        return data.get("messages", {}).get(session_id, [])

    def save_message(self, session_id: str, message: Dict[str, Any]) -> None:
        data = self._load_sessions_data()
        messages = data.setdefault("messages", {}).setdefault(session_id, [])
        msg_to_save = dict(message)
        if "id" not in msg_to_save:
            msg_to_save["id"] = str(uuid.uuid4())[:8]
        if "created_at" not in msg_to_save:
            msg_to_save["created_at"] = datetime.now(timezone.utc).isoformat()
        messages.append(msg_to_save)
        self._save_sessions_data(data)

    def delete_session(self, session_id: str) -> bool:
        data = self._load_sessions_data()
        sessions = data.get("sessions", [])
        filtered = [s for s in sessions if s["id"] != session_id]
        if len(filtered) < len(sessions):
            data["sessions"] = filtered
            data.get("messages", {}).pop(session_id, None)
            self._save_sessions_data(data)
            return True
        return False

    def record_query_run(self, sql: str, duration_ms: float, row_count: int, error: Optional[str] = None) -> None:
        self._ensure_dirs()
        runs: List[Dict[str, Any]] = []
        if self.query_runs_file.exists():
            try:
                runs = json.loads(self.query_runs_file.read_text(encoding="utf-8"))
            except Exception:
                runs = []
        run_record = {
            "id": str(uuid.uuid4())[:8],
            "sql": sql,
            "duration_ms": duration_ms,
            "row_count": row_count,
            "status": "error" if error else "success",
            "error": error or "",
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
        runs.insert(0, run_record)
        # Keep latest 200 runs
        runs = runs[:200]
        self.query_runs_file.write_text(json.dumps(runs, indent=2), encoding="utf-8")

    def get_query_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.query_runs_file.exists():
            try:
                runs = json.loads(self.query_runs_file.read_text(encoding="utf-8"))
                return runs[:limit]
            except Exception:
                return []
        return []

    def get_dashboard_tiles(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.tiles_file.exists():
            try:
                tiles = json.loads(self.tiles_file.read_text(encoding="utf-8"))
                if domain and domain != "global":
                    return [t for t in tiles if t.get("domain") in ["global", domain]]
                return tiles
            except Exception:
                return []
        return []

    def pin_tile(self, tile: Dict[str, Any], domain: str = "global") -> Dict[str, Any]:
        self._ensure_dirs()
        tiles = self.get_dashboard_tiles()
        new_tile = dict(tile)
        if "id" not in new_tile:
            new_tile["id"] = str(uuid.uuid4())[:8]
        new_tile["domain"] = tile.get("domain", domain)
        new_tile["created_at"] = datetime.now(timezone.utc).isoformat()
        tiles.insert(0, new_tile)
        self.tiles_file.write_text(json.dumps(tiles, indent=2), encoding="utf-8")
        return new_tile

    def unpin_tile(self, tile_id: str) -> bool:
        tiles = self.get_dashboard_tiles()
        filtered = [t for t in tiles if t.get("id") != tile_id]
        if len(filtered) < len(tiles):
            self.tiles_file.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
            return True
        return False


class DatabaseContextStorage(ContextStorage):
    """
    Centralized database-backed multi-domain storage (PostgreSQL, Supabase, Cloud SQL).
    Provides native schema/domain partitioning, cross-domain inheritance, and team collaboration.
    """

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
        engine_kwargs = {}
        if ":memory:" in self.connection_string:
            from sqlalchemy.pool import StaticPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            engine_kwargs["poolclass"] = StaticPool

        self.engine = create_engine(self.connection_string, **engine_kwargs)
        self.metadata = MetaData()

        self.domains_table = Table(
            "_vero_domains",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("display_name", String(128), nullable=False),
            Column("description", Text, default="")
        )

        self.rules_table = Table(
            "_vero_rules",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("domain", String(64), default="global"),
            Column("rule_text", Text, nullable=False),
            Column("updated_at", DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
        )

        self.metrics_table = Table(
            "_vero_metrics",
            self.metadata,
            Column("name", String(128), primary_key=True),
            Column("domain", String(64), primary_key=True, default="global"),
            Column("description", Text, default=""),
            Column("sql", Text, nullable=False),
            Column("updated_at", DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
        )

        self.schemas_table = Table(
            "_vero_schemas",
            self.metadata,
            Column("table_name", String(128), primary_key=True),
            Column("domain", String(64), default="global"),
            Column("schema_content", Text, nullable=False),
            Column("annotations", Text, default=""),
            Column("updated_at", DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
        )

        self.sessions_table = Table(
            "_vero_sessions",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("title", String(256), nullable=False),
            Column("domain", String(64), default="global"),
            Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
            Column("updated_at", DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
        )

        self.messages_table = Table(
            "_vero_messages",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("session_id", String(64), nullable=False),
            Column("role", String(32), nullable=False),
            Column("text", Text, default=""),
            Column("payload_json", Text, default=""),
            Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc))
        )

        self.query_runs_table = Table(
            "_vero_query_runs",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("sql", Text, nullable=False),
            Column("duration_ms", Float, default=0.0),
            Column("row_count", Integer, default=0),
            Column("status", String(32), default="success"),
            Column("error", Text, default=""),
            Column("executed_at", DateTime, default=lambda: datetime.now(timezone.utc))
        )

        self.tiles_table = Table(
            "_vero_dashboard_tiles",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("domain", String(64), default="global"),
            Column("title", String(256), nullable=False),
            Column("tile_type", String(32), default="chart"),
            Column("chart_type", String(32), default="bar"),
            Column("sql", Text, default=""),
            Column("data_json", Text, default=""),
            Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc))
        )

        # Create tables and seed default domains
        self.metadata.create_all(self.engine)
        self._seed_default_domains()

    def _seed_default_domains(self) -> None:
        defaults = [
            ("global", "Global (Shared)", "Enterprise-wide rules and definitions"),
            ("finance", "Finance", "Revenue, accounting, billing, and margin metrics"),
            ("marketing", "Marketing", "Campaigns, acquisition, ad-spend, and attribution"),
            ("product", "Product", "User engagement, retention, events, and features"),
        ]
        with self.engine.begin() as conn:
            for d_id, d_name, d_desc in defaults:
                exists = conn.execute(
                    text("SELECT 1 FROM _vero_domains WHERE id = :id"),
                    {"id": d_id}
                ).fetchone()
                if not exists:
                    conn.execute(
                        text("INSERT INTO _vero_domains (id, display_name, description) VALUES (:i, :n, :d)"),
                        {"i": d_id, "n": d_name, "d": d_desc}
                    )

    def get_domains(self) -> List[Dict[str, str]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, display_name, description FROM _vero_domains ORDER BY id = 'global' DESC, id ASC")
            ).fetchall()
            return [
                {"id": r[0], "name": r[1], "description": r[2]}
                for r in rows
            ]

    def get_rules(self, domain: str = "global") -> str:
        with self.engine.connect() as conn:
            global_res = conn.execute(
                text("SELECT rule_text FROM _vero_rules WHERE domain = 'global' ORDER BY id DESC LIMIT 1")
            ).fetchone()
            global_rules = global_res[0] if global_res else ""

            if domain == "global":
                return global_rules

            domain_res = conn.execute(
                text("SELECT rule_text FROM _vero_rules WHERE domain = :d ORDER BY id DESC LIMIT 1"),
                {"d": domain}
            ).fetchone()
            domain_rules = domain_res[0] if domain_res else ""

            parts = []
            if global_rules.strip():
                parts.append(global_rules.strip())
            if domain_rules.strip():
                parts.append(f"\n## [{domain.capitalize()} Domain Rules]\n{domain_rules.strip()}")
            return "\n".join(parts)

    def save_rules(self, rules: str, domain: str = "global") -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM _vero_rules WHERE domain = :d"), {"d": domain})
            conn.execute(
                text("INSERT INTO _vero_rules (domain, rule_text, updated_at) VALUES (:d, :r, :u)"),
                {"d": domain, "r": rules.strip(), "u": datetime.now(timezone.utc)}
            )

    def append_rule(self, rule: str, domain: str = "global") -> None:
        current = self.get_rules(domain=domain)
        clean_rule = rule.strip()
        if not clean_rule.startswith("- "):
            clean_rule = f"- {clean_rule}"
        header = f"# {domain.capitalize()} Analytics Rules\n\n" if not current.strip() else ""
        new_rules = f"{current.rstrip()}\n{clean_rule}\n" if current.strip() else f"{header}{clean_rule}\n"
        self.save_rules(new_rules, domain=domain)

    def get_metrics(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if domain and domain != "global":
                query = text("SELECT name, description, sql, domain FROM _vero_metrics WHERE domain IN ('global', :d) ORDER BY domain = 'global' DESC, name ASC")
                rows = conn.execute(query, {"d": domain}).fetchall()
            elif domain == "global":
                query = text("SELECT name, description, sql, domain FROM _vero_metrics WHERE domain = 'global' ORDER BY name ASC")
                rows = conn.execute(query).fetchall()
            else:
                query = text("SELECT name, description, sql, domain FROM _vero_metrics ORDER BY domain = 'global' DESC, name ASC")
                rows = conn.execute(query).fetchall()

            return [
                {"name": r[0], "description": r[1], "sql": r[2], "domain": r[3]}
                for r in rows
            ]

    def save_metric(self, metric: Dict[str, Any], domain: str = "global") -> None:
        target_domain = metric.get("domain", domain)
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM _vero_metrics WHERE name = :n AND domain = :d"),
                {"n": metric["name"], "d": target_domain}
            )
            conn.execute(
                text("INSERT INTO _vero_metrics (name, domain, description, sql, updated_at) VALUES (:n, :d, :desc, :s, :u)"),
                {
                    "n": metric["name"],
                    "d": target_domain,
                    "desc": metric.get("description", ""),
                    "s": metric.get("sql", ""),
                    "u": datetime.now(timezone.utc)
                }
            )

    def delete_metric(self, name: str, domain: str = "global") -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM _vero_metrics WHERE name = :n AND domain = :d"),
                {"n": name, "d": domain}
            )
            return res.rowcount > 0

    def get_schemas(self, domain: Optional[str] = None) -> Dict[str, str]:
        with self.engine.connect() as conn:
            if domain and domain != "global":
                query = text("SELECT table_name, schema_content, annotations, domain FROM _vero_schemas WHERE domain IN ('global', :d) ORDER BY table_name")
                rows = conn.execute(query, {"d": domain}).fetchall()
            elif domain == "global":
                query = text("SELECT table_name, schema_content, annotations, domain FROM _vero_schemas WHERE domain = 'global' ORDER BY table_name")
                rows = conn.execute(query).fetchall()
            else:
                query = text("SELECT table_name, schema_content, annotations, domain FROM _vero_schemas ORDER BY table_name")
                rows = conn.execute(query).fetchall()

            results = {}
            for r in rows:
                content = r[1]
                if r[2]:
                    content += f"\n\n## Business Notes & Annotations\n{r[2]}\n"
                results[r[0]] = content
            return results

    def save_schema(self, table_name: str, schema_md: str, domain: str = "global") -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM _vero_schemas WHERE table_name = :t"),
                {"t": table_name}
            )
            conn.execute(
                text("INSERT INTO _vero_schemas (table_name, domain, schema_content, updated_at) VALUES (:t, :d, :c, :u)"),
                {"t": table_name, "d": domain, "c": schema_md.strip(), "u": datetime.now(timezone.utc)}
            )

    def delete_schema(self, table_name: str) -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM _vero_schemas WHERE table_name = :t"),
                {"t": table_name}
            )
            return res.rowcount > 0

    def save_table_annotation(self, table_name: str, annotation: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE _vero_schemas SET annotations = :a, updated_at = :u WHERE table_name = :t"),
                {"a": annotation.strip(), "u": datetime.now(timezone.utc), "t": table_name}
            )

    # --- Session & History Persistence (Database) ---
    def get_sessions(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if domain and domain != "global":
                query = text("SELECT id, title, domain, created_at FROM _vero_sessions WHERE domain IN ('global', :d) ORDER BY created_at DESC")
                rows = conn.execute(query, {"d": domain}).fetchall()
            elif domain == "global":
                query = text("SELECT id, title, domain, created_at FROM _vero_sessions WHERE domain = 'global' ORDER BY created_at DESC")
                rows = conn.execute(query).fetchall()
            else:
                query = text("SELECT id, title, domain, created_at FROM _vero_sessions ORDER BY created_at DESC")
                rows = conn.execute(query).fetchall()

            return [
                {"id": r[0], "title": r[1], "domain": r[2], "created_at": str(r[3])}
                for r in rows
            ]

    def create_session(self, title: str, domain: str = "global") -> Dict[str, Any]:
        sess_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO _vero_sessions (id, title, domain, created_at, updated_at) VALUES (:i, :t, :d, :c, :u)"),
                {"i": sess_id, "t": title, "d": domain, "c": now, "u": now}
            )
        return {"id": sess_id, "title": title, "domain": domain, "created_at": now.isoformat()}

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, role, text, payload_json, created_at FROM _vero_messages WHERE session_id = :s ORDER BY created_at ASC"),
                {"s": session_id}
            ).fetchall()
            messages = []
            for r in rows:
                msg = {"id": r[0], "role": r[1], "text": r[2], "created_at": str(r[4])}
                if r[3]:
                    try:
                        msg.update(json.loads(r[3]))
                    except Exception:
                        pass
                messages.append(msg)
            return messages

    def save_message(self, session_id: str, message: Dict[str, Any]) -> None:
        msg_id = message.get("id", str(uuid.uuid4())[:8])
        role = message.get("role") or message.get("sender") or "user"
        text_content = message.get("text", "")
        # Store other fields in payload_json
        payload = {k: v for k, v in message.items() if k not in ["id", "role", "sender", "text", "session_id"]}
        payload_str = json.dumps(payload) if payload else ""

        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO _vero_messages (id, session_id, role, text, payload_json, created_at) VALUES (:i, :s, :r, :t, :p, :c)"),
                {
                    "i": msg_id,
                    "s": session_id,
                    "r": role,
                    "t": text_content,
                    "p": payload_str,
                    "c": datetime.now(timezone.utc)
                }
            )

    def delete_session(self, session_id: str) -> bool:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM _vero_messages WHERE session_id = :s"), {"s": session_id})
            res = conn.execute(text("DELETE FROM _vero_sessions WHERE id = :s"), {"s": session_id})
            return res.rowcount > 0

    def record_query_run(self, sql: str, duration_ms: float, row_count: int, error: Optional[str] = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO _vero_query_runs (sql, duration_ms, row_count, status, error, executed_at) VALUES (:s, :d, :r, :st, :e, :ex)"),
                {
                    "s": sql,
                    "d": duration_ms,
                    "r": row_count,
                    "st": "error" if error else "success",
                    "e": error or "",
                    "ex": datetime.now(timezone.utc)
                }
            )

    def get_query_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, sql, duration_ms, row_count, status, error, executed_at FROM _vero_query_runs ORDER BY id DESC LIMIT :lim"),
                {"lim": limit}
            ).fetchall()
            return [
                {
                    "id": str(r[0]),
                    "sql": r[1],
                    "duration_ms": r[2],
                    "row_count": r[3],
                    "status": r[4],
                    "error": r[5],
                    "executed_at": str(r[6])
                }
                for r in rows
            ]

    def get_dashboard_tiles(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if domain and domain != "global":
                query = text("SELECT id, domain, title, tile_type, chart_type, sql, data_json, created_at FROM _vero_dashboard_tiles WHERE domain IN ('global', :d) ORDER BY id DESC")
                rows = conn.execute(query, {"d": domain}).fetchall()
            else:
                query = text("SELECT id, domain, title, tile_type, chart_type, sql, data_json, created_at FROM _vero_dashboard_tiles ORDER BY id DESC")
                rows = conn.execute(query).fetchall()

            results = []
            for r in rows:
                tile = {
                    "id": r[0],
                    "domain": r[1],
                    "title": r[2],
                    "tile_type": r[3],
                    "chart_type": r[4],
                    "sql": r[5],
                    "created_at": str(r[7])
                }
                if r[6]:
                    try:
                        tile["data"] = json.loads(r[6])
                    except Exception:
                        tile["data"] = None
                results.append(tile)
            return results

    def pin_tile(self, tile: Dict[str, Any], domain: str = "global") -> Dict[str, Any]:
        tile_id = tile.get("id", str(uuid.uuid4())[:8])
        target_domain = tile.get("domain", domain)
        data_json = json.dumps(tile.get("data")) if tile.get("data") else ""
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO _vero_dashboard_tiles (id, domain, title, tile_type, chart_type, sql, data_json, created_at) VALUES (:i, :d, :t, :tt, :ct, :s, :dj, :c)"),
                {
                    "i": tile_id,
                    "d": target_domain,
                    "t": tile.get("title", "Untitled Metric"),
                    "tt": tile.get("tile_type", "chart"),
                    "ct": tile.get("chart_type", "bar"),
                    "s": tile.get("sql", ""),
                    "dj": data_json,
                    "c": now
                }
            )
        new_tile = dict(tile)
        new_tile["id"] = tile_id
        new_tile["domain"] = target_domain
        new_tile["created_at"] = now.isoformat()
        return new_tile

    def unpin_tile(self, tile_id: str) -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM _vero_dashboard_tiles WHERE id = :i"),
                {"i": tile_id}
            )
            return res.rowcount > 0
