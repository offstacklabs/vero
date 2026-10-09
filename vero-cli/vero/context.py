from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import yaml

from vero.config import VeroConfig
from vero.storage import (
    ContextStorage, LocalContextStorage, DatabaseContextStorage
)

class ContextEngine:
    def __init__(
        self,
        context_dir: Optional[Path] = None,
        storage: Optional[ContextStorage] = None,
        schemas: Optional[Dict[str, str]] = None,
        rules: Optional[str] = None,
        metrics: Optional[List[Dict[str, Any]]] = None,
        skills: Optional[Dict[str, str]] = None
    ):
        """
        ContextEngine supports:
        1. Local filesystem storage (.vero/)
        2. Centralized Database storage (PostgreSQL, Supabase, Cloud SQL) for team/cloud
        3. Stateless in-memory injection for serverless/multi-tenant microservices
        """
        self._in_memory_schemas = schemas
        self._in_memory_rules = rules
        self._in_memory_metrics = metrics
        self._in_memory_skills = skills

        if context_dir is None:
            self.context_dir = VeroConfig.get_workspace_root() / ".vero"
        else:
            self.context_dir = context_dir
            
        self.schemas_dir = self.context_dir / "schemas"
        self.skills_dir = self.context_dir / "skills"
        self.metrics_file = self.context_dir / "metrics.yaml"
        self.rules_file = self.context_dir / "RULES.md"

        # Initialize pluggable storage
        if storage is not None:
            self.storage = storage
        else:
            cfg = VeroConfig.load()
            if cfg.storage.backend in ["database", "postgres", "postgresql"] and cfg.storage.connection_string:
                self.storage = DatabaseContextStorage(cfg.storage.connection_string)
            else:
                self.storage = LocalContextStorage(self.context_dir)

    def initialize_workspace(self) -> None:
        """Initializes the .vero context directories, default rules, and metrics."""
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.schemas_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        if not self.rules_file.exists():
            default_rules = (
                "# Vero Analytics Rules\n\n"
                "## SQL Guidelines\n"
                "- Always use explicit column names instead of `SELECT *`.\n"
                "- For date filtering, prefer standard ISO dates (`YYYY-MM-DD`).\n"
                "- Always provide clean aliases for aggregated metrics (e.g. `COUNT(*) AS total_orders`).\n"
                "- Default to `LIMIT 50` unless otherwise specified by the user.\n"
            )
            self.save_rules(default_rules)
            
        if not self.metrics_file.exists():
            default_metrics = [
                {
                    "name": "active_users",
                    "description": "Count of users who have logged in within the last 30 days",
                    "sql": "COUNT(DISTINCT CASE WHEN last_login_date >= CURRENT_DATE - 30 THEN user_id END)"
                },
                {
                    "name": "arr",
                    "description": "Annual Recurring Revenue",
                    "sql": "SUM(monthly_subscription_amount * 12)"
                }
            ]
            for m in default_metrics:
                self.save_metric(m)

    def get_rules(self) -> str:
        if self._in_memory_rules is not None:
            return self._in_memory_rules
        return self.storage.get_rules()

    def save_rules(self, rules: str) -> None:
        self.storage.save_rules(rules)

    def append_rule(self, rule: str) -> None:
        self.storage.append_rule(rule)

    def get_metrics(self) -> List[Dict[str, Any]]:
        if self._in_memory_metrics is not None:
            return self._in_memory_metrics
        return self.storage.get_metrics()

    def save_metric(self, metric: Dict[str, Any]) -> None:
        self.storage.save_metric(metric)

    def delete_metric(self, name: str) -> bool:
        return self.storage.delete_metric(name)

    def get_schemas(self) -> Dict[str, str]:
        if self._in_memory_schemas is not None:
            return self._in_memory_schemas
        return self.storage.get_schemas()

    def save_table_annotation(self, table_name: str, annotation: str) -> None:
        self.storage.save_table_annotation(table_name, annotation)

    def sync_schemas(self, schema_info: Dict[str, Any]) -> None:
        """Converts introspected database schema into readable Markdown and saves to storage."""
        # Clean old schemas in storage
        current_schemas = set(schema_info.keys())
        existing = set(self.storage.get_schemas().keys())
        for removed in existing - current_schemas:
            self.storage.delete_schema(removed)

        overview_lines = [
            "# Database Schema Overview\n",
            "This folder contains the auto-synced schema definition for Vero AI.\n",
            f"**Total Tables/Views:** {len(schema_info)}\n\n",
            "## Entities\n"
        ]

        for table_name, details in schema_info.items():
            overview_lines.append(f"- [{table_name}](./{table_name}.md)")

            table_md = [
                f"# {'View' if details.get('is_view') else 'Table'}: `{table_name}`\n",
                "## Columns\n",
                "| Column Name | Data Type | Nullable | Default |",
                "| :--- | :--- | :--- | :--- |"
            ]
            for col in details["columns"]:
                table_md.append(f"| `{col['name']}` | `{col['type']}` | {col.get('nullable', True)} | {col.get('default', '')} |")

            if details.get("foreign_keys"):
                table_md.append("\n## Relationships & Foreign Keys\n")
                for fk in details["foreign_keys"]:
                    fk_constrained = ", ".join(fk['constrained_columns'])
                    fk_referred = ", ".join(fk['referred_columns'])
                    table_md.append(f"- `{fk_constrained}` -> `{fk['referred_table']}({fk_referred})`")

            self.storage.save_schema(table_name, "\n".join(table_md) + "\n")

        # Save overview to schemas_dir if local
        if isinstance(self.storage, LocalContextStorage):
            (self.schemas_dir / "README.md").write_text("\n".join(overview_lines) + "\n", encoding="utf-8")

    def get_full_context_prompt(self, query_hint: Optional[str] = None, max_tables: int = 15) -> str:
        """Compiles context into an LLM prompt from the active storage provider."""
        context_parts = []

        # 1. Rules
        rules = self.get_rules()
        if rules.strip():
            context_parts.append(f"=== RULES & GUIDELINES ===\n{rules.strip()}\n")

        # 2. Semantic Layer / Metrics
        metrics = self.get_metrics()
        if metrics:
            metrics_yaml = yaml.dump({"metrics": metrics}, default_flow_style=False)
            context_parts.append(f"=== SEMANTIC LAYER (METRICS) ===\n{metrics_yaml}\n")

        # 3. Database Schemas
        schemas = self.get_schemas()
        if schemas:
            table_names = list(schemas.keys())
            if query_hint and len(table_names) > max_tables:
                hint_lower = query_hint.lower()
                scored_tables = []
                for name in table_names:
                    score = hint_lower.count(name.lower())
                    if name.lower() in hint_lower.split():
                        score += 10
                    scored_tables.append((score, name))
                scored_tables.sort(key=lambda x: (-x[0], x[1]))
                table_names = [name for score, name in scored_tables[:max_tables]]

            schema_texts = [schemas[name] for name in sorted(table_names)]
            if schema_texts:
                context_parts.append("=== DATABASE SCHEMAS ===\n" + "\n\n".join(schema_texts) + "\n")

        # 4. Domain Skills
        if self._in_memory_skills is not None:
            skills_texts = [self._in_memory_skills[k] for k in sorted(self._in_memory_skills.keys())]
            if skills_texts:
                context_parts.append("=== DOMAIN SKILLS ===\n" + "\n\n".join(skills_texts) + "\n")
        elif self.skills_dir.exists():
            skills_texts = []
            for skill_path in sorted(self.skills_dir.glob("*.md")):
                skills_texts.append(skill_path.read_text(encoding="utf-8"))
            if skills_texts:
                context_parts.append("=== DOMAIN SKILLS ===\n" + "\n\n".join(skills_texts) + "\n")

        return "\n".join(context_parts)
