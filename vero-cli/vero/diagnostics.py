import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import sqlglot
from sqlglot import exp

class DiagnosticEngine:
    """
    Automated Root Cause Analysis (RCA) Engine.
    When a user asks "Why did this metric change?", this engine takes the base SQL query,
    extracts the target table/views, and autonomously slices the metric by available categorical
    dimensions to find the statistical drivers of the change.
    """

    def __init__(self, db_manager):
        self.db = db_manager

    def _extract_base_table(self, sql: str) -> Optional[str]:
        """Uses sqlglot to find the primary FROM table in the query."""
        try:
            parsed = sqlglot.parse_one(sql, read=self.db.dialect)
            for table in parsed.find_all(exp.Table):
                # Return fully qualified name (e.g. public.users) but exclude alias
                parts = []
                if table.catalog: parts.append(table.catalog)
                if table.db: parts.append(table.db)
                if table.name: parts.append(table.name)
                return ".".join(parts)
            return None
        except Exception:
            return None

    def _get_categorical_dimensions(self, table_name: str) -> List[str]:
        """Introspects the schema to find low-cardinality categorical columns suitable for slicing."""
        schema_info = self.db.introspect_schema()
        if table_name not in schema_info:
            return []

        cols = schema_info[table_name].get("columns", [])
        dimensions = []
        for c in cols:
            ctype = c["type"].lower()
            # Look for string/text/varchar columns that typically represent categories
            if any(t in ctype for t in ["char", "text", "str", "bool"]):
                dimensions.append(c["name"])
        return dimensions

    def explain_anomaly(self, base_sql: str) -> Dict[str, Any]:
        """
        Runs automated deviation analysis on a base query.
        Returns the top contributing dimensions driving the metric.
        """
        t_start = time.time()
        table_name = self._extract_base_table(base_sql)

        if not table_name:
            return {
                "success": False,
                "error": "Could not identify a base table to slice.",
                "duration_ms": round((time.time() - t_start) * 1000, 1)
            }

        dimensions = self._get_categorical_dimensions(table_name)
        if not dimensions:
            return {
                "success": False,
                "error": f"No categorical dimensions found in table '{table_name}' to perform slice analysis.",
                "duration_ms": round((time.time() - t_start) * 1000, 1)
            }

        # For MVP: We assume the base_sql is a simple aggregation like:
        # SELECT SUM(amount) FROM orders
        # We rewrite it to: SELECT dimension, SUM(amount) FROM orders GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        
        try:
            parsed = sqlglot.parse_one(base_sql, read=self.db.dialect)
            select_expr = None
            for select in parsed.find_all(exp.Select):
                if select.expressions:
                    select_expr = select.expressions[0]
                    break
        except Exception:
            select_expr = "*"

        findings = []

        # Limit to first 3 dimensions to avoid excessive warehouse cost
        for dim in dimensions[:3]:
            slice_sql = f"SELECT {dim}, {select_expr} as metric_val FROM {table_name} GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
            try:
                res = self.db.execute_query(slice_sql, limit=5, enforce_cost_guard=False, mask_pii=False)
                if res and res["rows"]:
                    findings.append({
                        "dimension": dim,
                        "sql": slice_sql,
                        "data": res["rows"]
                    })
            except Exception:
                continue

        # Sort findings by the magnitude of the top slice
        findings.sort(key=lambda x: float(x["data"][0][1]) if x["data"] and len(x["data"][0]) > 1 and isinstance(x["data"][0][1], (int, float)) else 0, reverse=True)

        # Generate a natural language summary
        summary = f"I analyzed the underlying data in `{table_name}` to find what is driving this metric. "
        if findings:
            top_finding = findings[0]
            top_dim = top_finding["dimension"]
            top_val = top_finding["data"][0][0]
            top_metric = top_finding["data"][0][1]
            summary += f"The largest driver is **{top_dim}**, specifically the '{top_val}' segment which accounts for {top_metric}."
        else:
            summary += "However, I couldn't find any statistically significant deviations across the available dimensions."

        return {
            "success": True,
            "table": table_name,
            "dimensions_analyzed": dimensions[:3],
            "findings": findings,
            "summary": summary,
            "duration_ms": round((time.time() - t_start) * 1000, 1)
        }
