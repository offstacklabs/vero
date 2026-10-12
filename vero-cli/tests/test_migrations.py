import pytest
from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect

def test_alembic_migrations_lifecycle(tmp_path):
    test_db_path = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{test_db_path}"

    ini_path = Path(__file__).parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Run migrations upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # 2. Verify all core metadata tables created (revisions 001, 002, 003)
    assert "_vero_domains" in tables
    assert "_vero_rules" in tables
    assert "_vero_metrics" in tables
    assert "_vero_schemas" in tables
    assert "_vero_sessions" in tables
    assert "_vero_messages" in tables
    assert "_vero_query_runs" in tables
    assert "_vero_dashboard_tiles" in tables
    assert "_vero_users" in tables
    assert "_vero_audit_logs" in tables

    # 3. Verify telemetry columns added in revision 002
    query_runs_cols = [c["name"] for c in inspector.get_columns("_vero_query_runs")]
    assert "bytes_scanned" in query_runs_cols
    assert "cost_usd" in query_runs_cols

    # 4. Verify DatabaseContextStorage integrates with Alembic
    from vero.storage import DatabaseContextStorage
    storage = DatabaseContextStorage(db_url)
    res = storage.migrate()
    assert res["status"] == "ok"
