import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml

from vero.config import VeroConfig
from vero.context import ContextEngine

class DbtSyncEngine:
    def __init__(self, context_engine: Optional[ContextEngine] = None):
        self.context_engine = context_engine or ContextEngine()

    def find_manifest(self, project_path: Path) -> Path:
        """Locates manifest.json within a dbt project directory or target folder."""
        if project_path.is_file() and project_path.name == "manifest.json":
            return project_path

        candidates = [
            project_path / "target" / "manifest.json",
            project_path / "manifest.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not locate manifest.json in {project_path} or {project_path / 'target'}.")

    def parse_manifest(self, manifest_path: Path) -> Dict[str, Any]:
        """Loads and parses the dbt manifest JSON file."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def sync(self, project_or_manifest_path: Path) -> Dict[str, Any]:
        """
        Parses dbt manifest and synchronizes models, columns, descriptions,
        relationships, and semantic metrics into the Vero context.
        """
        manifest_file = self.find_manifest(project_or_manifest_path)
        manifest = self.parse_manifest(manifest_file)

        nodes = manifest.get("nodes", {})
        models: Dict[str, Any] = {}
        relationships: List[Dict[str, str]] = []

        # 1. First pass: extract tests to discover relationships
        for node_id, node in nodes.items():
            if node.get("resource_type") == "test":
                test_metadata = node.get("test_metadata", {})
                if test_metadata.get("name") == "relationships":
                    kwargs = test_metadata.get("kwargs", {})
                    field = kwargs.get("field")
                    to_model = kwargs.get("to")
                    to_field = kwargs.get("to_field", "id")
                    
                    # Target node is attached in depends_on
                    depends_on_nodes = node.get("depends_on", {}).get("nodes", [])
                    from_model = None
                    for dep in depends_on_nodes:
                        if dep.startswith("model."):
                            from_model = dep.split(".")[-1]
                            break

                    if from_model and field and to_model:
                        to_name = to_model.replace("ref('", "").replace("')", "").split(".")[-1]
                        relationships.append({
                            "from_model": from_model,
                            "from_column": field,
                            "to_model": to_name,
                            "to_column": to_field
                        })

        # 2. Extract models & documentation
        schemas_dir = self.context_engine.schemas_dir
        schemas_dir.mkdir(parents=True, exist_ok=True)

        synced_models_count = 0
        for node_id, node in nodes.items():
            if node.get("resource_type") == "model":
                model_name = node.get("name")
                description = node.get("description", "").strip()
                columns_meta = node.get("columns", {})

                # Find relationships for this model
                model_fks = [
                    r for r in relationships if r["from_model"] == model_name
                ]

                # Format Markdown schema
                lines = [
                    f"# Model: `{model_name}`\n",
                ]
                if description:
                    lines.append(f"**Description:** {description}\n")

                lines.extend([
                    "## Columns\n",
                    "| Column Name | Data Type | Description |",
                    "| :--- | :--- | :--- |"
                ])

                for col_name, col_data in columns_meta.items():
                    dtype = col_data.get("data_type") or "UNKNOWN"
                    cdesc = col_data.get("description", "").replace("\n", " ").strip()
                    lines.append(f"| `{col_name}` | `{dtype}` | {cdesc or '-'} |")

                if model_fks:
                    lines.append("\n## Relationships & Foreign Keys\n")
                    for fk in model_fks:
                        lines.append(f"- `{fk['from_column']}` -> `{fk['to_model']}({fk['to_column']})`")

                model_file = schemas_dir / f"{model_name}.md"
                model_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
                synced_models_count += 1
                models[model_name] = {
                    "columns": len(columns_meta),
                    "relationships": len(model_fks),
                    "description": bool(description)
                }

        # 3. Extract metrics / semantic layer
        metrics = manifest.get("metrics", {})
        synced_metrics = []

        for metric_id, metric_node in metrics.items():
            m_name = metric_node.get("name")
            m_desc = metric_node.get("description", "")
            m_type = metric_node.get("type", "")
            m_calc = metric_node.get("calculation_method") or metric_node.get("sql") or ""

            synced_metrics.append({
                "name": m_name,
                "description": m_desc or f"dbt metric ({m_type})",
                "sql": m_calc or m_name
            })

        if synced_metrics:
            # Merge with existing metrics
            existing_metrics = []
            if self.context_engine.metrics_file.exists():
                try:
                    with open(self.context_engine.metrics_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                        existing_metrics = data.get("metrics", [])
                except Exception:
                    pass

            # Combine without duplicates
            combined_names = {m["name"] for m in synced_metrics}
            final_metrics = synced_metrics + [m for m in existing_metrics if m["name"] not in combined_names]

            with open(self.context_engine.metrics_file, "w", encoding="utf-8") as f:
                yaml.dump({"metrics": final_metrics}, f, default_flow_style=False, sort_keys=False)

        # 4. Generate catalog README overview
        overview_lines = [
            "# dbt Semantic Catalog Overview\n",
            f"**Total Synced Models:** {synced_models_count}\n",
            f"**Total Synced Metrics:** {len(synced_metrics)}\n\n",
            "## Models\n"
        ]
        for m_name in sorted(models.keys()):
            overview_lines.append(f"- [{m_name}](./{m_name}.md)")

        (schemas_dir / "README.md").write_text("\n".join(overview_lines) + "\n", encoding="utf-8")

        return {
            "models_synced": synced_models_count,
            "metrics_synced": len(synced_metrics),
            "models": models
        }
