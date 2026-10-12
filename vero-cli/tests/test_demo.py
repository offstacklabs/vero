import pytest
import duckdb
from pathlib import Path
from vero.demo import provision_demo
from vero.db import DatabaseManager

def test_provision_demo_warehouse(tmp_path):
    db_file = provision_demo(workspace_root=tmp_path)
    assert db_file.exists()

    # 1. Verify DuckDB tables created and populated
    con = duckdb.connect(str(db_file), read_only=True)
    tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
    assert "customers" in tables
    assert "subscriptions" in tables
    assert "invoices" in tables
    assert "mrr_movements" in tables

    # 2. Check customer count
    cust_count = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    assert cust_count == 12

    # 3. Check MRR sum
    active_mrr = con.execute("SELECT SUM(mrr_amount) FROM subscriptions WHERE status = 'active'").fetchone()[0]
    assert active_mrr > 40000

    con.close()

    # 4. Verify DatabaseManager executes query against demo warehouse
    db = DatabaseManager(dialect="duckdb", connection_string=f"duckdb:///{db_file.resolve()}")
    res = db.execute_query("SELECT name, industry FROM customers LIMIT 5")
    assert res["row_count"] == 5
    assert len(res["columns"]) == 2

    # 5. Verify context files created
    assert (tmp_path / ".vero" / "RULES.md").exists()
    assert (tmp_path / ".vero" / "metrics.yaml").exists()
    assert (tmp_path / ".vero" / "config.yaml").exists()
