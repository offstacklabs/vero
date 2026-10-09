from pathlib import Path
from typing import Dict, Any, List, Optional
import json

from vero.config import VeroConfig

class ContextEngine:
    def __init__(self, context_dir: Optional[Path] = None):
        if context_dir is None:
            self.context_dir = VeroConfig.get_workspace_root() / ".vero"
        else:
            self.context_dir = context_dir
            
        self.schemas_dir = self.context_dir / "schemas"
        self.skills_dir = self.context_dir / "skills"
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
                "- Default to `LIMIT 50` unless otherwise specified by the user.\n\n"
                "## Business Context\n"
                "- Active users are defined as users with `status = 'active'` who have logged in within the last 30 days.\n"
            )
            self.rules_file.write_text(default_rules, encoding="utf-8")

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
        """Compiles context into a prompt. Optionally filters schemas based on naive keyword matching to save tokens."""
        context_parts = []

        if self.rules_file.exists():
            context_parts.append(f"=== RULES & GUIDELINES ===\n{self.rules_file.read_text(encoding='utf-8')}\n")

        if self.schemas_dir.exists():
            schema_paths = list(self.schemas_dir.glob("*.md"))
            schema_paths = [p for p in schema_paths if p.name != "README.md"]
            
            # Simple keyword matching for pruning if a hint is provided
            if query_hint and len(schema_paths) > max_tables:
                hint_lower = query_hint.lower()
                # Score tables by occurrence in the query hint
                scored_paths = []
                for p in schema_paths:
                    score = hint_lower.count(p.stem.lower())
                    # Boost score if table name is exact match or very likely relevant
                    if p.stem.lower() in hint_lower.split():
                        score += 10
                    scored_paths.append((score, p))
                
                # Sort by score descending, then fallback to alphabetical to be deterministic
                scored_paths.sort(key=lambda x: (-x[0], x[1].name))
                schema_paths = [p for score, p in scored_paths[:max_tables]]

            schema_texts = []
            for schema_path in sorted(schema_paths):
                schema_texts.append(schema_path.read_text(encoding="utf-8"))
            if schema_texts:
                context_parts.append("=== DATABASE SCHEMAS ===\n" + "\n\n".join(schema_texts) + "\n")

        if self.skills_dir.exists():
            skills_texts = []
            for skill_path in sorted(self.skills_dir.glob("*.md")):
                skills_texts.append(skill_path.read_text(encoding="utf-8"))
            if skills_texts:
                context_parts.append("=== DOMAIN SKILLS ===\n" + "\n\n".join(skills_texts) + "\n")

        return "\n".join(context_parts)
