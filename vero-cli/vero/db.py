from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import duckdb
import sqlglot

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
                self._duckdb_con = duckdb.connect(db_path if db_path else ":memory:", read_only=True if db_path else False)
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

    def execute_query(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Safely executes a read-only query and returns headers and rows."""
        cleaned_query = query.strip().rstrip(";")
        
        if not self.is_safe_query(cleaned_query):
            raise ValueError("Query rejected: Only pure SELECT statements are allowed in read-only mode, or query has syntax errors.")

        if self.dialect == "duckdb":
            con = self.get_engine()
            # DuckDB doesn't have a simple statement timeout yet, rely on read-only conn
            res = con.execute(cleaned_query)
            columns = [desc[0] for desc in res.description]
            rows = res.fetchmany(limit)
            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows)
            }
        else:
            engine = self.get_engine()
            with engine.connect() as conn:
                # Basic execution timeout attempt (dialect dependent, Postgres supports statement_timeout)
                if self.dialect == "postgresql" or self.dialect == "postgres":
                    conn.execute(text("SET statement_timeout = '30s'"))
                
                result = conn.execute(text(cleaned_query))
                columns = list(result.keys())
                rows = result.fetchmany(limit)
                return {
                    "columns": columns,
                    "rows": [list(row) for row in rows],
                    "row_count": len(rows)
                }
