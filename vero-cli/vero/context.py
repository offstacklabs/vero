from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import yaml

from vero.config import VeroConfig

class ContextEngine:
    def __init__(
        self,
        context_dir: Optional[Path] = None,
        schemas: Optional[Dict[str, str]] = None,
        rules: Optional[str] = None,
        metrics: Optional[List[Dict[str, Any]]] = None,
        skills: Optional[Dict[str, str]] = None
    ):
        """
        ContextEngine supports both local filesystem storage (.vero/) and
        stateless in-memory injection for commercial/multi-tenant cloud deployments.
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

    def initialize_workspace(self) -> None:
        """Initializes the .vero context directories and default rules."""
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
            self.rules_file.write_text(default_rules, encoding="utf-8")
            
        if not self.metrics_file.exists():
            default_metrics = (
                "metrics:\n"
                "  - name: active_users\n"
                "    description: 'Count of users who have logged in within the last 30 days'\n"
                "    sql: 'COUNT(DISTINCT CASE WHEN last_login_date >= CURRENT_DATE - 30 THEN user_id END)'\n"
                "  - name: arr\n"
                "    description: 'Annual Recurring Revenue'\n"
                "    sql: 'SUM(monthly_subscription_amount * 12)'\n"
            )
            self.metrics_file.write_text(default_metrics, encoding="utf-8")

    def sync_schemas(self, schema_info: Dict[str, Any]) -> None:
        """Converts introspected database schema into readable Markdown context files."""
        self.schemas_dir.mkdir(parents=True, exist_ok=True)

        # Cleanup old schemas that are no longer in the DB
        existing_schemas = {p.stem for p in self.schemas_dir.glob("*.md") if p.name != "README.md"}
        current_schemas = set(schema_info.keys())
        for removed in existing_schemas - current_schemas:
            (self.schemas_dir / f"{removed}.md").unlink()

        # Overview file
        overview_lines = [
            "# Database Schema Overview\n",
            "This folder contains the auto-synced schema definition for Vero AI.\n",
            f"**Total Tables/Views:** {len(schema_info)}\n\n",
            "## Entities\n"
        ]

        for table_name, details in schema_info.items():
            overview_lines.append(f"- [{table_name}](./{table_name}.md)")

            # Individual table schema markdown
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

            table_file = self.schemas_dir / f"{table_name}.md"
            table_file.write_text("\n".join(table_md) + "\n", encoding="utf-8")

        (self.schemas_dir / "README.md").write_text("\n".join(overview_lines) + "\n", encoding="utf-8")

    def get_full_context_prompt(self, query_hint: Optional[str] = None, max_tables: int = 15) -> str:
        """Compiles context into a prompt. Optionally filters schemas based on keyword matching."""
        context_parts = []

        # 1. Rules
        if self._in_memory_rules is not None:
            context_parts.append(f"=== RULES & GUIDELINES ===\n{self._in_memory_rules.strip()}\n")
        elif self.rules_file.exists():
            context_parts.append(f"=== RULES & GUIDELINES ===\n{self.rules_file.read_text(encoding='utf-8')}\n")

        # 2. Semantic Layer / Metrics
        if self._in_memory_metrics is not None:
            metrics_yaml = yaml.dump({"metrics": self._in_memory_metrics}, default_flow_style=False)
            context_parts.append(f"=== SEMANTIC LAYER (METRICS) ===\n{metrics_yaml}\n")
        elif self.metrics_file.exists():
            context_parts.append(f"=== SEMANTIC LAYER (METRICS) ===\n{self.metrics_file.read_text(encoding='utf-8')}\n")

        # 3. Database Schemas
        if self._in_memory_schemas is not None:
            table_names = list(self._in_memory_schemas.keys())
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

            schema_texts = [self._in_memory_schemas[name] for name in sorted(table_names)]
            if schema_texts:
                context_parts.append("=== DATABASE SCHEMAS ===\n" + "\n\n".join(schema_texts) + "\n")
        elif self.schemas_dir.exists():
            schema_paths = list(self.schemas_dir.glob("*.md"))
            schema_paths = [p for p in schema_paths if p.name != "README.md"]
            
            if query_hint and len(schema_paths) > max_tables:
                hint_lower = query_hint.lower()
                scored_paths = []
                for p in schema_paths:
                    score = hint_lower.count(p.stem.lower())
                    if p.stem.lower() in hint_lower.split():
                        score += 10
                    scored_paths.append((score, p))
                
                scored_paths.sort(key=lambda x: (-x[0], x[1].name))
                schema_paths = [p for score, p in scored_paths[:max_tables]]

            schema_texts = []
            for schema_path in sorted(schema_paths):
                schema_texts.append(schema_path.read_text(encoding="utf-8"))
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
