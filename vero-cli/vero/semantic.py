import os
import re
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from vero.context import ContextEngine

class SemanticMetric(BaseModel):
    name: str
    domain: str = "global"
    description: str = ""
    sql: str
    metric_type: str = "custom" # "sum", "count", "average", "ratio", "custom"
    source_table: Optional[str] = None
    dimensions: List[str] = Field(default_factory=list)
    imported_from: str = "native" # "native", "lookml", "dbt", "cube"

    def to_vero_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "sql": self.sql,
            "metadata_json": json.dumps({
                "metric_type": self.metric_type,
                "source_table": self.source_table,
                "dimensions": self.dimensions,
                "imported_from": self.imported_from
            })
        }

class LookMLParser:
    """
    Parses Looker LookML (.view.lkml, .explore.lkml) into Vero native semantic metrics.
    Translates LookML measures (sum, count, count_distinct, average, number) and dimensions.
    """

    @staticmethod
    def parse_content(content: str, domain: str = "global", view_name: Optional[str] = None) -> List[SemanticMetric]:
        metrics: List[SemanticMetric] = []

        if not view_name:
            view_match = re.search(r"view:\s*([a-zA-Z0-9_]+)\s*\{", content)
            if view_match:
                view_name = view_match.group(1)

        # Split content into measure blocks manually to avoid regex greediness issues
        measure_blocks = []
        in_measure = False
        current_block = ""
        current_name = ""
        brace_count = 0

        for line in content.splitlines():
            line_stripped = line.strip()
            if not in_measure and line_stripped.startswith("measure:"):
                in_measure = True
                m = re.match(r"measure:\s*([a-zA-Z0-9_]+)", line_stripped)
                current_name = m.group(1) if m else "unknown"
                current_block = line + "\n"
                brace_count += line.count('{') - line.count('}')
            elif in_measure:
                current_block += line + "\n"
                brace_count += line.count('{') - line.count('}')
                if brace_count <= 0:
                    measure_blocks.append((current_name, current_block))
                    in_measure = False
                    current_block = ""

        for name, body in measure_blocks:
            type_match = re.search(r"type:\s*([a-zA-Z0-9_]+)", body)
            m_type = type_match.group(1).lower() if type_match else "custom"

            sql_match = re.search(r"sql:\s*([^;]+);;", body)
            raw_sql = sql_match.group(1).strip() if sql_match else None

            desc_match = re.search(r'description:\s*"([^"]+)"', body)
            desc = desc_match.group(1).strip() if desc_match else ""

            clean_expr = raw_sql
            if raw_sql:
                clean_expr = re.sub(r"\$\{([a-zA-Z0-9_\.]+)\}", r"\1", raw_sql).strip()

            if m_type == "count":
                formula = f"COUNT(*)"
            elif m_type == "count_distinct":
                formula = f"COUNT(DISTINCT {clean_expr or 'id'})"
            elif m_type == "sum":
                formula = f"SUM({clean_expr})" if clean_expr else f"SUM({name})"
            elif m_type == "average":
                formula = f"AVG({clean_expr})" if clean_expr else f"AVG({name})"
            else:
                formula = clean_expr or name

            metrics.append(SemanticMetric(
                name=name,
                domain=domain,
                description=desc,
                sql=formula,
                metric_type=m_type,
                source_table=view_name,
                imported_from="lookml"
            ))

        return metrics

class DbtSemanticParser:
    """
    Parses dbt Core Semantic Layer (manifest.json / semantic_models) into Vero metrics.
    """

    @staticmethod
    def parse_manifest(manifest_data: Dict[str, Any], domain: str = "global") -> List[SemanticMetric]:
        metrics: List[SemanticMetric] = []

        # 1. Parse modern dbt semantic_models (MetricFlow)
        semantic_models = manifest_data.get("semantic_models", {})
        for sm_key, sm in semantic_models.items():
            model_name = sm.get("name", "")
            node_rel = sm.get("node_relation", {})
            table_name = node_rel.get("alias") or node_rel.get("relation_name") or model_name

            for measure in sm.get("measures", []):
                m_name = measure.get("name")
                agg = measure.get("agg", "sum").lower()
                expr = measure.get("expr") or m_name
                desc = measure.get("description", "")

                if agg == "sum":
                    sql = f"SUM({expr})"
                elif agg in ["count", "count_distinct"]:
                    sql = f"COUNT(DISTINCT {expr})" if agg == "count_distinct" else f"COUNT({expr})"
                elif agg == "average":
                    sql = f"AVG({expr})"
                else:
                    sql = f"{agg.upper()}({expr})"

                metrics.append(SemanticMetric(
                    name=m_name,
                    domain=domain,
                    description=desc,
                    sql=sql,
                    metric_type=agg,
                    source_table=table_name,
                    imported_from="dbt"
                ))

        # 2. Parse top-level metrics in manifest
        dbt_metrics = manifest_data.get("metrics", {})
        for m_key, m in dbt_metrics.items():
            name = m.get("name")
            desc = m.get("description", "")
            m_type = m.get("type", "simple")
            type_params = m.get("type_params", {})
            measure_ref = type_params.get("measure") or type_params.get("expr") or name

            metrics.append(SemanticMetric(
                name=name,
                domain=domain,
                description=desc,
                sql=str(measure_ref),
                metric_type=m_type,
                imported_from="dbt"
            ))

        return metrics

class CubeSchemaParser:
    """
    Parses Cube.js schema (YAML or JSON export) into Vero native semantic metrics.
    """

    @staticmethod
    def parse_content(content: Union[str, Dict[str, Any]], domain: str = "global") -> List[SemanticMetric]:
        metrics: List[SemanticMetric] = []

        if isinstance(content, str):
            try:
                data = yaml.safe_load(content)
            except Exception:
                try:
                    data = json.loads(content)
                except Exception:
                    data = {}
        else:
            data = content

        cubes = data.get("cubes", []) if isinstance(data, dict) else []
        for cube in cubes:
            cube_name = cube.get("name", "")
            table_name = cube.get("sql_table") or cube_name

            measures = cube.get("measures", [])
            for m in measures:
                name = m.get("name")
                m_type = m.get("type", "sum").lower()
                sql_expr = m.get("sql") or name
                desc = m.get("description", "")

                if m_type == "count":
                    sql = "COUNT(*)"
                elif m_type == "count_distinct":
                    sql = f"COUNT(DISTINCT {sql_expr})"
                elif m_type == "sum":
                    sql = f"SUM({sql_expr})"
                elif m_type in ["avg", "average"]:
                    sql = f"AVG({sql_expr})"
                else:
                    sql = f"{m_type.upper()}({sql_expr})"

                metrics.append(SemanticMetric(
                    name=f"{cube_name}_{name}" if cube_name else name,
                    domain=domain,
                    description=desc,
                    sql=sql,
                    metric_type=m_type,
                    source_table=table_name,
                    imported_from="cube"
                ))

        return metrics

class SemanticImporter:
    """
    Unified manager for importing and synchronizing semantic metrics
    from Looker (LookML), dbt (MetricFlow), and Cube into Vero's native semantic engine.
    """

    def __init__(self, context_engine: Optional[ContextEngine] = None):
        self.engine = context_engine or ContextEngine()

    def import_lookml(self, source: Union[str, Path], domain: str = "global") -> List[SemanticMetric]:
        """Parses LookML files or string content."""
        if isinstance(source, (str, Path)) and (Path(source).is_file() or Path(source).is_dir()):
            p = Path(source)
            files = [p] if p.is_file() else list(p.rglob("*.lkml"))
            all_metrics = []
            for f in files:
                text_content = f.read_text(encoding="utf-8")
                all_metrics.extend(LookMLParser.parse_content(text_content, domain=domain, view_name=f.stem.replace(".view", "")))
            return all_metrics
        else:
            return LookMLParser.parse_content(str(source), domain=domain)

    def import_dbt(self, source: Union[str, Path, Dict[str, Any]], domain: str = "global") -> List[SemanticMetric]:
        """Parses dbt manifest.json file or dictionary."""
        if isinstance(source, (str, Path)) and Path(source).is_file():
            data = json.loads(Path(source).read_text(encoding="utf-8"))
        elif isinstance(source, str):
            data = json.loads(source)
        else:
            data = source
        return DbtSemanticParser.parse_manifest(data, domain=domain)

    def import_cube(self, source: Union[str, Path, Dict[str, Any]], domain: str = "global") -> List[SemanticMetric]:
        """Parses Cube.js schema file or string."""
        if isinstance(source, (str, Path)) and Path(source).is_file():
            raw = Path(source).read_text(encoding="utf-8")
            return CubeSchemaParser.parse_content(raw, domain=domain)
        else:
            return CubeSchemaParser.parse_content(source, domain=domain)

    def sync_to_vero(self, metrics: List[SemanticMetric], domain: str = "global") -> int:
        """Saves a batch of imported metrics to Vero's central metadata storage."""
        count = 0
        for m in metrics:
            self.engine.save_metric(m.to_vero_dict(), domain=domain)
            count += 1
        return count
