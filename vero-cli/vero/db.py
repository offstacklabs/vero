from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import duckdb
import sqlglot

def format_bytes(bytes_num: int) -> str:
    """Formats raw bytes count into human-readable string (B, KB, MB, GB, TB)."""
    if bytes_num <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    val = float(bytes_num)
    while val >= 1024.0 and i < len(units) - 1:
        val /= 1024.0
        i += 1
    return f"{val:.1f} {units[i]}" if i > 0 else f"{int(val)} B"


class DatabaseManager:
    def __init__(self, dialect: str, connection_string: str):
        self.dialect = dialect.lower()
        self.connection_string = connection_string
        self._engine: Optional[Engine] = None
        self._duckdb_con = None

    def get_engine(self):
        if self.dialect == "duckdb":
            if not self._duckdb_con:
                db_path = self.connection_string.replace("duckdb:///", "").replace("duckdb://", "")
                is_mem = not db_path or db_path == ":memory:"
                self._duckdb_con = duckdb.connect(":memory:" if is_mem else db_path, read_only=False if is_mem else True)
            return self._duckdb_con
        else:
            if not self._engine:
                connect_args = {}
                if self.dialect == "sqlite":
                    connect_args = {"check_same_thread": False}
                    # enforce URI read-only if not in memory
                    if ":memory:" not in self.connection_string and "mode=ro" not in self.connection_string:
                        # pysqlite requires uri=true as a query param
                        if self.connection_string.startswith("sqlite:///"):
                            db_path = self.connection_string[10:]
                            self.connection_string = f"sqlite:///file:{db_path}?mode=ro&uri=true"
                        elif self.connection_string.startswith("sqlite://"):
                            db_path = self.connection_string[9:]
                            self.connection_string = f"sqlite://file:{db_path}?mode=ro&uri=true"

                self._engine = create_engine(self.connection_string, connect_args=connect_args)
            return self._engine

    def is_safe_query(self, query: str) -> bool:
        """Uses sqlglot to ensure the query only contains SELECT statements, including inside CTEs."""
        try:
            # Parse all statements in the query
            statements = sqlglot.parse(query, read=self.dialect)
            if not statements:
                return False
            for stmt in statements:
                if not stmt:
                    continue
                # Only allow Select and CTEs
                if not isinstance(stmt, (sqlglot.exp.Select, sqlglot.exp.Subquery)):
                    return False
                
                # Deeply inspect for any mutating expressions (Delete, Insert, Update, Drop, Create, Alter)
                mutating_types = (
                    sqlglot.exp.Delete,
                    sqlglot.exp.Insert,
                    sqlglot.exp.Update,
                    sqlglot.exp.Drop,
                    sqlglot.exp.Create,
                    sqlglot.exp.Alter,
                )
                for node in stmt.find_all(mutating_types):
                    return False
                
            return True
        except sqlglot.errors.ParseError:
            # If we can't parse it, we must reject it to be safe
            return False

    def introspect_schema(self) -> Dict[str, Any]:
        """Extracts schema, tables, columns, data types, and foreign keys."""
        if self.dialect == "duckdb":
            con = self.get_engine()
            tables = con.execute("SHOW TABLES").fetchall()
            schema_info = {}
            for (table_name,) in tables:
                cols = con.execute(f"DESCRIBE {table_name}").fetchall()
                schema_info[table_name] = {
                    "columns": [
                        {"name": col[0], "type": col[1], "nullable": col[2] == "YES"}
                        for col in cols
                    ],
                    "foreign_keys": []
                }
            return schema_info
        else:
            engine = self.get_engine()
            inspector = inspect(engine)
            schema_info = {}
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                fks = inspector.get_foreign_keys(table_name)
                schema_info[table_name] = {
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True),
                            "default": str(col.get("default", ""))
                        }
                        for col in columns
                    ],
                    "foreign_keys": [
                        {
                            "constrained_columns": fk["constrained_columns"],
                            "referred_table": fk["referred_table"],
                            "referred_columns": fk["referred_columns"],
                        }
                        for fk in fks
                    ]
                }
            # Attempt to introspect views as well
            try:
                for view_name in inspector.get_view_names():
                    columns = inspector.get_columns(view_name)
                    schema_info[view_name] = {
                        "columns": [
                            {
                                "name": col["name"],
                                "type": str(col["type"]),
                                "nullable": col.get("nullable", True),
                                "default": str(col.get("default", ""))
                            }
                            for col in columns
                        ],
                        "foreign_keys": [],
                        "is_view": True
                    }
            except Exception:
                pass # Some dialects might not support get_view_names cleanly

            return schema_info

    def estimate_query_cost(self, query: str) -> Dict[str, Any]:
        """
        Runs dry-run compilation against BigQuery or EXPLAIN on other warehouses
        to estimate data volume (bytes scanned) and monetary cost before execution.
        """
        cleaned_query = query.strip().rstrip(";")
        if not self.is_safe_query(cleaned_query):
            return {
                "valid": False,
                "error": "Query rejected by AST safety checker (mutations detected or syntax invalid)",
                "bytes_scanned": 0,
                "bytes_formatted": "0 B",
                "cost_usd": 0.0,
                "cost_guard_passed": False
            }

        # Dialect: BigQuery Native Dry Run
        if self.dialect == "bigquery":
            try:
                from google.cloud import bigquery
                project_id = None
                if "bigquery://" in self.connection_string:
                    parts = self.connection_string.replace("bigquery://", "").split("/")
                    if parts and parts[0]:
                        project_id = parts[0]
                client = bigquery.Client(project=project_id)
                job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
                query_job = client.query(cleaned_query, job_config=job_config)
                
                bytes_scanned = query_job.total_bytes_processed or 0
                cost_usd = round((bytes_scanned / (1024 ** 4)) * 6.25, 4)
                
                # Check safety guard
                from vero.config import VeroConfig
                cfg = VeroConfig.load()
                max_bytes = cfg.cost_guard.max_bytes_scanned if cfg.cost_guard else 10 * 1024 * 1024 * 1024
                cost_guard_passed = bytes_scanned <= max_bytes

                return {
                    "valid": True,
                    "dialect": "bigquery",
                    "bytes_scanned": bytes_scanned,
                    "bytes_formatted": format_bytes(bytes_scanned),
                    "cost_usd": cost_usd,
                    "cost_guard_passed": cost_guard_passed,
                    "max_allowed_bytes": max_bytes,
                    "statement_type": query_job.statement_type or "SELECT",
                    "referenced_tables": [f"{t.project}.{t.dataset_id}.{t.table_id}" for t in query_job.referenced_tables] if query_job.referenced_tables else []
                }
            except Exception as e:
                return {
                    "valid": False,
                    "dialect": "bigquery",
                    "error": str(e),
                    "bytes_scanned": 0,
                    "bytes_formatted": "0 B",
                    "cost_usd": 0.0,
                    "cost_guard_passed": False
                }

        # Other dialects fallback: run EXPLAIN
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                explain_res = conn.execute(text(f"EXPLAIN {cleaned_query}"))
                lines = [str(r[0]) for r in explain_res.fetchall()]
                return {
                    "valid": True,
                    "dialect": self.dialect,
                    "bytes_scanned": 0,
                    "bytes_formatted": "0 B (Warehouse compute)",
                    "cost_usd": 0.0,
                    "cost_guard_passed": True,
                    "explain_plan": lines[:4]
                }
        except Exception as e:
            return {
                "valid": False,
                "dialect": self.dialect,
                "error": str(e),
                "bytes_scanned": 0,
                "bytes_formatted": "0 B",
                "cost_usd": 0.0,
                "cost_guard_passed": False
            }

    def execute_query(
        self,
        query: str,
        limit: int = 100,
        enforce_cost_guard: bool = False,
        mask_pii: bool = True
    ) -> Dict[str, Any]:
        """Safely executes a read-only query and returns headers, rows, cost metrics, and governance info."""
        cleaned_query = query.strip().rstrip(";")
        
        if not self.is_safe_query(cleaned_query):
            raise ValueError("Query rejected: Only pure SELECT statements are allowed in read-only mode, or query has syntax errors.")

        # Pre-execution Cost Guard
        estimate = None
        if enforce_cost_guard and self.dialect == "bigquery":
            estimate = self.estimate_query_cost(cleaned_query)
            if estimate["valid"] and not estimate.get("cost_guard_passed", True):
                raise ValueError(
                    f"Cost Guard Blocked: Query projected to scan {estimate['bytes_formatted']}, "
                    f"exceeding safety limit of {format_bytes(estimate['max_allowed_bytes'])}. Query cancelled."
                )

        if self.dialect == "duckdb":
            con = self.get_engine()
            res = con.execute(cleaned_query)
            columns = [desc[0] for desc in res.description]
            raw_rows = res.fetchmany(limit)
            rows = [list(row) for row in raw_rows]
        else:
            engine = self.get_engine()
            with engine.connect() as conn:
                if self.dialect == "postgresql" or self.dialect == "postgres":
                    conn.execute(text("SET statement_timeout = '30s'"))
                
                result = conn.execute(text(cleaned_query))
                columns = list(result.keys())
                raw_rows = result.fetchmany(limit)
                rows = [list(row) for row in raw_rows]

        # Apply Enterprise Data Governance & PII Masking
        masked_columns = []
        if mask_pii and rows:
            try:
                from vero.config import VeroConfig
                from vero.governance import DataGovernanceEngine
                gov_cfg = VeroConfig.load().governance
                if gov_cfg and gov_cfg.enabled:
                    gov = DataGovernanceEngine(
                        enabled=gov_cfg.enabled,
                        auto_detect_pii=gov_cfg.auto_detect_pii,
                        custom_rules=gov_cfg.rules
                    )
                    rows, masked_columns = gov.mask_dataset(columns, rows)
            except Exception:
                pass

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "bytes_scanned": estimate.get("bytes_scanned", 0) if estimate else 0,
            "bytes_formatted": estimate.get("bytes_formatted", "0 B") if estimate else "0 B",
            "cost_usd": estimate.get("cost_usd", 0.0) if estimate else 0.0,
            "cost_guard_passed": estimate.get("cost_guard_passed", True) if estimate else True,
            "masked_columns": masked_columns
        }
