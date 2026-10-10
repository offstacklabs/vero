import pytest
from vero.db import DatabaseManager

def test_safe_queries():
    db = DatabaseManager("sqlite", "sqlite:///:memory:")
    
    # Safe queries
    assert db.is_safe_query("SELECT * FROM users") is True
    assert db.is_safe_query("WITH cte AS (SELECT 1) SELECT * FROM cte") is True
    
    # Unsafe queries
    assert db.is_safe_query("DROP TABLE users") is False
    assert db.is_safe_query("DELETE FROM users WHERE id = 1") is False
    assert db.is_safe_query("UPDATE users SET name = 'admin'") is False
    assert db.is_safe_query("INSERT INTO users (id) VALUES (1)") is False
    
    # Injection/Stacking
    assert db.is_safe_query("SELECT * FROM users; DROP TABLE users") is False
    assert db.is_safe_query("WITH cte AS (DELETE FROM users RETURNING *) SELECT * FROM cte") is False

def test_execute_blocked():
    db = DatabaseManager("sqlite", "sqlite:///:memory:")
    with pytest.raises(ValueError, match="Query rejected"):
        db.execute_query("DROP TABLE users")

def test_format_bytes():
    from vero.db import format_bytes
    assert format_bytes(0) == "0 B"
    assert format_bytes(512) == "512 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.0 GB"
    assert format_bytes(1099511627776) == "1.0 TB"

def test_sqlite_explain_estimate():
    db = DatabaseManager("sqlite", "sqlite:///:memory:")
    con = db.get_engine()
    from sqlalchemy import text
    with con.connect() as conn:
        conn.execute(text("CREATE TABLE items (id INT);"))
        conn.commit()

    est = db.estimate_query_cost("SELECT * FROM items")
    assert est["valid"] is True
    assert est["dialect"] == "sqlite"
    assert est["cost_guard_passed"] is True

def test_bigquery_cost_guard_blocked():
    from unittest.mock import patch, MagicMock
    db = DatabaseManager("bigquery", "bigquery://my-project/dataset")
    
    with patch("google.cloud.bigquery.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_job = MagicMock()
        # 15 GB scanned (> 10 GB limit)
        mock_job.total_bytes_processed = 15 * 1024 * 1024 * 1024
        mock_job.statement_type = "SELECT"
        mock_job.referenced_tables = []
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client

        est = db.estimate_query_cost("SELECT * FROM large_table")
        assert est["valid"] is True
        assert est["bytes_scanned"] == 15 * 1024 * 1024 * 1024
        assert est["bytes_formatted"] == "15.0 GB"
        assert est["cost_guard_passed"] is False
        assert est["cost_usd"] > 0

        # When executed with enforce_cost_guard=True, should raise ValueError
        with pytest.raises(ValueError, match="Cost Guard Blocked"):
            db.execute_query("SELECT * FROM large_table", enforce_cost_guard=True)

def test_calculate_warehouse_cost():
    from vero.db import calculate_warehouse_cost
    # 1 TB BigQuery = $6.25
    assert calculate_warehouse_cost("bigquery", bytes_scanned=1024**4) == 6.25
    # Snowflake X-Small (1 credit/hr @ $3.00/credit) for 3600s = $3.00
    assert calculate_warehouse_cost("snowflake", duration_ms=3600000) == 3.00
    # Postgres @ $0.10/hr for 3600s = $0.10
    assert calculate_warehouse_cost("postgres", duration_ms=3600000) == 0.10
    # DuckDB / SQLite = $0.00
    assert calculate_warehouse_cost("duckdb", bytes_scanned=1000000, duration_ms=500) == 0.0
    assert calculate_warehouse_cost("sqlite", bytes_scanned=1000000, duration_ms=500) == 0.0
