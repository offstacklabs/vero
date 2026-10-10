import pytest
from unittest.mock import MagicMock
from vero.diagnostics import DiagnosticEngine
from vero.db import DatabaseManager

def test_extract_base_table():
    db = DatabaseManager(dialect="bigquery", connection_string="")
    engine = DiagnosticEngine(db)

    # 1. Simple table
    assert engine._extract_base_table("SELECT SUM(amount) FROM sales") == "sales"
    assert engine._extract_base_table("SELECT * FROM public.users WHERE active=1") == "public.users"

    # 2. Join
    assert engine._extract_base_table("SELECT * FROM orders o JOIN customers c ON o.cid = c.id") == "orders"

    # 3. No table
    assert engine._extract_base_table("SELECT 1") is None

def test_explain_anomaly():
    db = MagicMock()
    db.dialect = "sqlite"
    db.introspect_schema.return_value = {
        "sales": {
            "columns": [
                {"name": "id", "type": "int"},
                {"name": "region", "type": "varchar"},
                {"name": "status", "type": "text"},
                {"name": "amount", "type": "float"}
            ]
        }
    }
    
    # Mocking execution to return fake slice data
    def mock_execute(sql, **kwargs):
        if "region" in sql:
            return {"rows": [["EMEA", 5000], ["NA", 3000], ["APAC", 1000]]}
        if "status" in sql:
            return {"rows": [["Shipped", 8000], ["Pending", 1000]]}
        return {"rows": []}

    db.execute_query.side_effect = mock_execute

    engine = DiagnosticEngine(db)
    res = engine.explain_anomaly("SELECT SUM(amount) FROM sales WHERE year = 2026")

    assert res["success"] is True
    assert res["table"] == "sales"
    assert "region" in res["dimensions_analyzed"]
    assert "status" in res["dimensions_analyzed"]

    # Status shipped has the highest value (8000) so it should be the top driver
    assert res["findings"][0]["dimension"] == "status"
    assert "Shipped" in res["summary"]
    assert "8000" in res["summary"]

    # Verify query rewrite
    assert "SELECT status, SUM(amount) as metric_val FROM sales GROUP BY 1" in res["findings"][0]["sql"]
