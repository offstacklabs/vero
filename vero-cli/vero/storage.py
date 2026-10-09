from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import yaml
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, text, Table, Column, String, Text, MetaData, Integer, DateTime
)

class ContextStorage(ABC):
    """Abstract interface for pluggable context persistence."""

    @abstractmethod
    def get_rules(self) -> str:
        """Returns business and SQL guidelines."""
        pass

    @abstractmethod
    def save_rules(self, rules: str) -> None:
        """Overwrites business and SQL guidelines."""
        pass

    @abstractmethod
    def append_rule(self, rule: str) -> None:
        """Appends a new business rule."""
        pass

    @abstractmethod
    def get_metrics(self) -> List[Dict[str, Any]]:
        """Returns all registered semantic metrics."""
        pass

    @abstractmethod
    def save_metric(self, metric: Dict[str, Any]) -> None:
        """Creates or updates a semantic metric."""
        pass

    @abstractmethod
    def delete_metric(self, name: str) -> bool:
        """Deletes a metric by name."""
        pass

    @abstractmethod
    def get_schemas(self) -> Dict[str, str]:
        """Returns all table schemas as {table_name: schema_markdown}."""
        pass

    @abstractmethod
    def save_schema(self, table_name: str, schema_md: str) -> None:
        """Saves a table schema markdown."""
        pass

    @abstractmethod
    def delete_schema(self, table_name: str) -> bool:
        """Deletes a table schema."""
        pass

    @abstractmethod
    def save_table_annotation(self, table_name: str, annotation: str) -> None:
        """Attaches custom business notes/annotations to a table."""
        pass


class LocalContextStorage(ContextStorage):
    """File-based context storage for local/offline developer workflows."""

    def __init__(self, context_dir: Path):
        self.context_dir = context_dir
        self.schemas_dir = self.context_dir / "schemas"
        self.metrics_file = self.context_dir / "metrics.yaml"
        self.rules_file = self.context_dir / "RULES.md"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.schemas_dir.mkdir(parents=True, exist_ok=True)

    def get_rules(self) -> str:
        if self.rules_file.exists():
            return self.rules_file.read_text(encoding="utf-8")
        return ""

    def save_rules(self, rules: str) -> None:
        self._ensure_dirs()
        self.rules_file.write_text(rules.strip() + "\n", encoding="utf-8")

    def append_rule(self, rule: str) -> None:
        current = self.get_rules()
        clean_rule = rule.strip()
        if not clean_rule.startswith("- "):
            clean_rule = f"- {clean_rule}"
        new_rules = f"{current.rstrip()}\n{clean_rule}\n" if current.strip() else f"# Vero Analytics Rules\n\n{clean_rule}\n"
        self.save_rules(new_rules)

    def get_metrics(self) -> List[Dict[str, Any]]:
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    return data.get("metrics", [])
            except Exception:
                return []
        return []

    def save_metric(self, metric: Dict[str, Any]) -> None:
        self._ensure_dirs()
        metrics = self.get_metrics()
        updated = False
        for i, m in enumerate(metrics):
            if m.get("name") == metric.get("name"):
                metrics[i] = metric
                updated = True
                break
        if not updated:
            metrics.append(metric)

        with open(self.metrics_file, "w", encoding="utf-8") as f:
            yaml.dump({"metrics": metrics}, f, default_flow_style=False, sort_keys=False)

    def delete_metric(self, name: str) -> bool:
        metrics = self.get_metrics()
        filtered = [m for m in metrics if m.get("name") != name]
        if len(filtered) < len(metrics):
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                yaml.dump({"metrics": filtered}, f, default_flow_style=False, sort_keys=False)
            return True
        return False

    def get_schemas(self) -> Dict[str, str]:
        results = {}
        if self.schemas_dir.exists():
            for p in sorted(self.schemas_dir.glob("*.md")):
                if p.name != "README.md":
                    results[p.stem] = p.read_text(encoding="utf-8")
        return results

    def save_schema(self, table_name: str, schema_md: str) -> None:
        self._ensure_dirs()
        file_path = self.schemas_dir / f"{table_name}.md"
        file_path.write_text(schema_md.strip() + "\n", encoding="utf-8")

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
            # Replace existing annotation section
            parts = current_md.split("## Business Notes & Annotations")
            new_md = parts[0].rstrip() + annotation_block
        else:
            new_md = current_md.rstrip() + annotation_block
            
        file_path.write_text(new_md, encoding="utf-8")


class DatabaseContextStorage(ContextStorage):
    """
    Centralized database-backed context storage (PostgreSQL, Supabase, Cloud SQL, etc.)
    Enables shared team workspaces, multi-tenancy, and persistent metadata in serverless environments.
    """

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
        # In-memory SQLite requires StaticPool to share state across multiple connection calls
        engine_kwargs = {}
        if ":memory:" in self.connection_string:
            from sqlalchemy.pool import StaticPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            engine_kwargs["poolclass"] = StaticPool

        self.engine = create_engine(self.connection_string, **engine_kwargs)
        self.metadata = MetaData()

        self.rules_table = Table(
            "_vero_rules",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("rule_text", Text, nullable=False),
            Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        )

        self.metrics_table = Table(
            "_vero_metrics",
            self.metadata,
            Column("name", String(128), primary_key=True),
            Column("description", Text, default=""),
            Column("sql", Text, nullable=False),
            Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        )

        self.schemas_table = Table(
            "_vero_schemas",
            self.metadata,
            Column("table_name", String(128), primary_key=True),
            Column("schema_content", Text, nullable=False),
            Column("annotations", Text, default=""),
            Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        )

        # Automatically ensure metadata tables exist
        self.metadata.create_all(self.engine)

    def get_rules(self) -> str:
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT rule_text FROM _vero_rules ORDER BY id DESC LIMIT 1")
            ).fetchone()
            if result:
                return result[0]
        return ""

    def save_rules(self, rules: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM _vero_rules"))
            conn.execute(
                text("INSERT INTO _vero_rules (rule_text, updated_at) VALUES (:r, :u)"),
                {"r": rules.strip(), "u": datetime.now(timezone.utc)}
            )

    def append_rule(self, rule: str) -> None:
        current = self.get_rules()
        clean_rule = rule.strip()
        if not clean_rule.startswith("- "):
            clean_rule = f"- {clean_rule}"
        new_rules = f"{current.rstrip()}\n{clean_rule}\n" if current.strip() else f"# Vero Analytics Rules\n\n{clean_rule}\n"
        self.save_rules(new_rules)

    def get_metrics(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT name, description, sql FROM _vero_metrics ORDER BY name")
            ).fetchall()
            return [
                {"name": r[0], "description": r[1], "sql": r[2]}
                for r in rows
            ]

    def save_metric(self, metric: Dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            # Upsert
            conn.execute(
                text("DELETE FROM _vero_metrics WHERE name = :n"),
                {"n": metric["name"]}
            )
            conn.execute(
                text("INSERT INTO _vero_metrics (name, description, sql, updated_at) VALUES (:n, :d, :s, :u)"),
                {
                    "n": metric["name"],
                    "d": metric.get("description", ""),
                    "s": metric.get("sql", ""),
                    "u": datetime.now(timezone.utc)
                }
            )

    def delete_metric(self, name: str) -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM _vero_metrics WHERE name = :n"),
                {"n": name}
            )
            return res.rowcount > 0

    def get_schemas(self) -> Dict[str, str]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT table_name, schema_content, annotations FROM _vero_schemas ORDER BY table_name")
            ).fetchall()
            results = {}
            for r in rows:
                content = r[1]
                if r[2]:  # Append annotations if present
                    content += f"\n\n## Business Notes & Annotations\n{r[2]}\n"
                results[r[0]] = content
            return results

    def save_schema(self, table_name: str, schema_md: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM _vero_schemas WHERE table_name = :t"),
                {"t": table_name}
            )
            conn.execute(
                text("INSERT INTO _vero_schemas (table_name, schema_content, updated_at) VALUES (:t, :c, :u)"),
                {"t": table_name, "c": schema_md.strip(), "u": datetime.now(timezone.utc)}
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
