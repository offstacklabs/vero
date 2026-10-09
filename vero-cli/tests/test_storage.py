import pytest
from pathlib import Path
from vero.storage import LocalContextStorage, DatabaseContextStorage
from vero.context import ContextEngine

def test_local_context_storage(tmp_path: Path):
    storage = LocalContextStorage(tmp_path / ".vero")
    
    # 1. Rules
    storage.save_rules("# Rules\n- Limit 50")
    assert "- Limit 50" in storage.get_rules()
    storage.append_rule("Filter test users")
    assert "- Filter test users" in storage.get_rules()

    # 2. Metrics
    storage.save_metric({"name": "cac", "description": "Customer Acquisition Cost", "sql": "SUM(marketing)/COUNT(users)"})
    metrics = storage.get_metrics()
    assert len(metrics) == 1
    assert metrics[0]["name"] == "cac"
    
    # Delete metric
    assert storage.delete_metric("cac") is True
    assert len(storage.get_metrics()) == 0

    # 3. Schemas & Annotations
    storage.save_schema("users", "# Table: users\n| id | INT |")
    schemas = storage.get_schemas()
    assert "users" in schemas
    assert "id" in schemas["users"]

    storage.save_table_annotation("users", "Primary user accounts table.")
    assert "Primary user accounts table." in storage.get_schemas()["users"]

def test_database_context_storage():
    # Use SQLite in-memory to test database storage functionality
    db_storage = DatabaseContextStorage("sqlite:///:memory:")

    # 1. Rules
    db_storage.save_rules("# Corporate Rules\n- Use ISO dates")
    assert "- Use ISO dates" in db_storage.get_rules()
    db_storage.append_rule("Exclude test tenants")
    assert "- Exclude test tenants" in db_storage.get_rules()

    # 2. Metrics
    db_storage.save_metric({"name": "ltv", "description": "Lifetime Value", "sql": "SUM(revenue)/COUNT(users)"})
    metrics = db_storage.get_metrics()
    assert len(metrics) == 1
    assert metrics[0]["name"] == "ltv"

    # Upsert metric
    db_storage.save_metric({"name": "ltv", "description": "Updated LTV", "sql": "SUM(net_revenue)/COUNT(users)"})
    assert db_storage.get_metrics()[0]["description"] == "Updated LTV"

    # Delete metric
    assert db_storage.delete_metric("ltv") is True
    assert len(db_storage.get_metrics()) == 0

    # 3. Schemas & Annotations
    db_storage.save_schema("orders", "# Table: orders\n| id | INT |\n| amount | FLOAT |")
    schemas = db_storage.get_schemas()
    assert "orders" in schemas
    assert "amount" in schemas["orders"]

    db_storage.save_table_annotation("orders", "Verified order facts table.")
    assert "Verified order facts table." in db_storage.get_schemas()["orders"]

def test_context_engine_with_database_storage():
    db_storage = DatabaseContextStorage("sqlite:///:memory:")
    engine = ContextEngine(storage=db_storage)

    engine.save_rules("Default LIMIT 10")
    engine.save_metric({"name": "churn", "description": "Churn rate", "sql": "lost/total"})
    engine.save_table_annotation("customers", "Core customer model")

    prompt = engine.get_full_context_prompt()
    assert "Default LIMIT 10" in prompt
    assert "churn" in prompt

def test_database_storage_multi_domain():
    db_storage = DatabaseContextStorage("sqlite:///:memory:")

    # 1. Domains exist
    domains = [d["id"] for d in db_storage.get_domains()]
    assert "global" in domains
    assert "finance" in domains
    assert "marketing" in domains

    # 2. Domain Rules Inheritance
    db_storage.save_rules("- Global standard: default LIMIT 50", domain="global")
    db_storage.save_rules("- Fiscal year begins in February", domain="finance")

    finance_rules = db_storage.get_rules(domain="finance")
    assert "Global standard: default LIMIT 50" in finance_rules
    assert "Fiscal year begins in February" in finance_rules

    # 3. Domain Metric Collision Resolution
    db_storage.save_metric({"name": "revenue", "description": "GAAP Recognized Revenue", "sql": "SUM(recognized_amount)"}, domain="finance")
    db_storage.save_metric({"name": "revenue", "description": "Attributed Campaign GMV", "sql": "SUM(campaign_gmv)"}, domain="marketing")

    finance_metrics = {m["name"]: m["sql"] for m in db_storage.get_metrics(domain="finance")}
    marketing_metrics = {m["name"]: m["sql"] for m in db_storage.get_metrics(domain="marketing")}

    assert finance_metrics["revenue"] == "SUM(recognized_amount)"
    assert marketing_metrics["revenue"] == "SUM(campaign_gmv)"

    # 4. Domain Schema Partitioning
    db_storage.save_schema("invoices", "# Table: invoices\n| id | INT |", domain="finance")
    db_storage.save_schema("campaigns", "# Table: campaigns\n| id | INT |", domain="marketing")

    finance_schemas = db_storage.get_schemas(domain="finance")
    assert "invoices" in finance_schemas
    assert "campaigns" not in finance_schemas

    # 5. ContextEngine Prompt Generation with Domain Scope
    engine = ContextEngine(storage=db_storage)
    finance_prompt = engine.get_full_context_prompt(domain="finance")
    assert "invoices" in finance_prompt
    assert "campaigns" not in finance_prompt
    assert "Fiscal year begins in February" in finance_prompt
