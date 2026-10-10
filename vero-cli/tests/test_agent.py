import pytest
from unittest.mock import MagicMock
from vero.agent import VeroAgent
from vero.db import DatabaseManager
from vero.context import ContextEngine
from vero.config import VeroConfig, DatabaseConfig

def test_self_healing_reflection_loop():
    # Setup DuckDB in-memory database
    db = DatabaseManager(dialect="duckdb", connection_string="duckdb:///:memory:")
    con = db.get_engine()
    con.execute("CREATE TABLE products (id INTEGER, title VARCHAR, price DOUBLE);")
    con.execute("INSERT INTO products VALUES (1, 'Widget', 19.99);")

    agent = VeroAgent(
        config=VeroConfig(database=DatabaseConfig(dialect="duckdb", connection_string="duckdb:///:memory:")),
        db_manager=db,
        context_engine=ContextEngine(schemas={"products": "# Table: products\n| id | INT |\n| title | VARCHAR |\n| price | DOUBLE |"})
    )

    # 1. Initial SQL has invalid column 'name' instead of 'title'
    agent.generate_sql = MagicMock(return_value={
        "thought": "Querying products by name",
        "sql": "SELECT name FROM products",
        "explanation": "Select product name",
        "suggested_visualization": "table",
        "tables_used": ["products"]
    })

    # 2. Reflect & heal fixes the query to use 'title'
    agent.reflect_and_heal = MagicMock(return_value={
        "thought": "Fixed column from name to title based on DuckDB error",
        "sql": "SELECT title FROM products",
        "explanation": "Select product title",
        "suggested_visualization": "table",
        "tables_used": ["products"]
    })

    result = agent.ask("Show product titles", execute=True, max_retries=2)

    # Verification:
    # 1. Reflection loop was triggered
    assert agent.reflect_and_heal.called
    assert len(result["reflection_steps"]) == 1
    assert "name" in result["reflection_steps"][0]["error"].lower()
    
    # 2. Healed query succeeded
    assert result["error"] is None
    assert result["sql"] == "SELECT title FROM products"
    assert result["data"] is not None
    assert result["data"]["rows"] == [["Widget"]]

def test_agent_telemetry_tracking():
    db = DatabaseManager(dialect="sqlite", connection_string="sqlite:///:memory:")
    con = db.get_engine()
    from sqlalchemy import text
    with con.connect() as conn:
        conn.execute(text("CREATE TABLE metrics (val INT);"))
        conn.execute(text("INSERT INTO metrics VALUES (42);"))
        conn.commit()

    agent = VeroAgent(
        config=VeroConfig(database=DatabaseConfig(dialect="sqlite", connection_string="sqlite:///:memory:")),
        db_manager=db,
        context_engine=ContextEngine()
    )

    agent.generate_sql = MagicMock(return_value={
        "thought": "Get metric",
        "sql": "SELECT val FROM metrics",
        "explanation": "Return metric",
        "suggested_visualization": "table",
        "tables_used": ["metrics"],
        "_telemetry": {
            "prompt_tokens": 850,
            "completion_tokens": 120,
            "total_tokens": 970,
            "llm_cost_usd": 0.0033
        }
    })

    result = agent.ask("Get metric")
    assert result["error"] is None
    assert "telemetry" in result
    tel = result["telemetry"]
    assert tel["prompt_tokens"] == 850
    assert tel["completion_tokens"] == 120
    assert tel["total_tokens"] == 970
    assert tel["llm_cost_usd"] == 0.0033
    assert "spans" in tel
    assert tel["spans"]["total_ms"] >= 0
