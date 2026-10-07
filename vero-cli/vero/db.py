from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import duckdb

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
                self._duckdb_con = duckdb.connect(db_path if db_path else ":memory:")
            return self._duckdb_con
        else:
            if not self._engine:
                self._engine = create_engine(self.connection_string)
            return self._engine

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
            return schema_info

    def execute_query(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Safely executes a read-only query and returns headers and rows."""
        cleaned_query = query.strip().rstrip(";")
        
        # Basic SQL safety check: disallow mutations
        forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "REPLACE"]
        first_word = cleaned_query.split()[0].upper() if cleaned_query else ""
        if first_word in forbidden:
            raise ValueError(f"Write operation '{first_word}' is forbidden in read-only mode.")

        if self.dialect == "duckdb":
            con = self.get_engine()
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
                result = conn.execute(text(cleaned_query))
                columns = list(result.keys())
                rows = result.fetchmany(limit)
                return {
                    "columns": columns,
                    "rows": [list(row) for row in rows],
                    "row_count": len(rows)
                }
