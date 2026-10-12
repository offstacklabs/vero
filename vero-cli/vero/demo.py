import os
import duckdb
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel

console = Console()

DEMO_RULES = """# Business Rules & Guidelines (B2B SaaS Demo)

## Revenue & Accounting
- Monthly Recurring Revenue (MRR) is derived strictly from `subscriptions` where `status = 'active'`.
- Annual Recurring Revenue (ARR) is defined as `MRR * 12`.
- One-time setup fees, professional services, and refunds are recorded in `invoices` but must NEVER be added to MRR.
- Fiscal year begins on January 1st and follows standard calendar quarters (Q1: Jan-Mar, Q2: Apr-Jun, Q3: Jul-Sep, Q4: Oct-Dec).

## Customer Segmentation
- Customers with MRR > $1,000/mo are categorized as 'Enterprise'.
- Customers with MRR between $200 and $1,000/mo are 'Mid-Market'.
- Customers with MRR < $200/mo are 'Starter'.
- Churned subscriptions are marked with `status = 'canceled'`.
"""

DEMO_METRICS = """# Verified Semantic Metrics
- name: mrr
  description: "Monthly Recurring Revenue from all active subscriptions"
  sql: "SUM(mrr_amount)"
  domain: "global"

- name: arr
  description: "Annualized Run-Rate (MRR * 12)"
  sql: "SUM(mrr_amount) * 12"
  domain: "global"

- name: active_subscribers
  description: "Count of unique paying customers with active contracts"
  sql: "COUNT(DISTINCT customer_id)"
  domain: "global"

- name: gross_churn_usd
  description: "Total monthly revenue lost to cancellations"
  sql: "SUM(churned_mrr)"
  domain: "global"

- name: total_invoiced
  description: "Gross invoiced cash collected across all billing periods"
  sql: "SUM(amount_usd)"
  domain: "global"
"""

def provision_demo(workspace_root: Optional[Path] = None) -> Path:
    """
    Initializes a zero-config demo environment with an embedded DuckDB
    B2B SaaS warehouse, verified semantic metrics, and context rules.
    """
    root = workspace_root or Path.cwd()
    context_dir = root / ".vero"
    context_dir.mkdir(parents=True, exist_ok=True)
    db_file = context_dir / "demo_warehouse.duckdb"

    # 1. Create and Seed Embedded DuckDB Warehouse
    con = duckdb.connect(str(db_file), read_only=False)

    con.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY,
        name VARCHAR,
        industry VARCHAR,
        tier VARCHAR,
        country VARCHAR,
        signed_up_at DATE
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        plan_name VARCHAR,
        mrr_amount DECIMAL(10, 2),
        status VARCHAR,
        started_at DATE
    );

    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        invoice_date DATE,
        amount_usd DECIMAL(10, 2),
        status VARCHAR
    );

    CREATE TABLE IF NOT EXISTS mrr_movements (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        movement_month VARCHAR,
        new_mrr DECIMAL(10, 2),
        expansion_mrr DECIMAL(10, 2),
        contraction_mrr DECIMAL(10, 2),
        churned_mrr DECIMAL(10, 2)
    );
    """)

    # Seed Customers
    con.execute("""
    DELETE FROM customers;
    INSERT INTO customers VALUES
    (1, 'Acme Corp', 'Fintech', 'Enterprise', 'United States', '2025-01-15'),
    (2, 'Globex Digital', 'E-commerce', 'Enterprise', 'Germany', '2025-02-01'),
    (3, 'Soylent AI', 'Healthcare', 'Mid-Market', 'United States', '2025-02-18'),
    (4, 'Initech Software', 'Logistics', 'Mid-Market', 'United States', '2025-03-05'),
    (5, 'Umbrella Security', 'Cybersecurity', 'Enterprise', 'United Kingdom', '2025-03-12'),
    (6, 'Hooli Cloud', 'Cloud Infrastructure', 'Enterprise', 'United States', '2025-04-01'),
    (7, 'Massive Media', 'Advertising', 'Enterprise', 'France', '2025-04-20'),
    (8, 'Stark Analytics', 'Defense & Aerospace', 'Enterprise', 'United States', '2025-05-02'),
    (9, 'Wayne Industrial', 'Manufacturing', 'Enterprise', 'United States', '2025-05-15'),
    (10, 'Cyberdyne Data', 'Robotics', 'Starter', 'Japan', '2025-06-01'),
    (11, 'Vandelay Industries', 'Import/Export', 'Starter', 'United States', '2025-06-15'),
    (12, 'Dunder Mifflin', 'Retail Supplies', 'Starter', 'United States', '2025-07-01');
    """)

    # Seed Subscriptions
    con.execute("""
    DELETE FROM subscriptions;
    INSERT INTO subscriptions VALUES
    (101, 1, 'Enterprise Annual', 4500.00, 'active', '2025-01-15'),
    (102, 2, 'Enterprise Growth', 3200.00, 'active', '2025-02-01'),
    (103, 3, 'Pro Team', 850.00, 'active', '2025-02-18'),
    (104, 4, 'Pro Team', 750.00, 'active', '2025-03-05'),
    (105, 5, 'Enterprise Annual', 6000.00, 'active', '2025-03-12'),
    (106, 6, 'Enterprise Custom', 8500.00, 'active', '2025-04-01'),
    (107, 7, 'Enterprise Growth', 3500.00, 'active', '2025-04-20'),
    (108, 8, 'Enterprise Custom', 12000.00, 'active', '2025-05-02'),
    (109, 9, 'Enterprise Annual', 5500.00, 'active', '2025-05-15'),
    (110, 10, 'Starter Monthly', 150.00, 'active', '2025-06-01'),
    (111, 11, 'Starter Monthly', 120.00, 'canceled', '2025-06-15'),
    (112, 12, 'Starter Monthly', 99.00, 'active', '2025-07-01');
    """)

    # Seed Invoices
    con.execute("""
    DELETE FROM invoices;
    INSERT INTO invoices VALUES
    (1001, 1, '2026-01-01', 4500.00, 'paid'),
    (1002, 2, '2026-01-01', 3200.00, 'paid'),
    (1003, 3, '2026-01-01', 850.00, 'paid'),
    (1004, 4, '2026-01-01', 750.00, 'paid'),
    (1005, 5, '2026-01-01', 6000.00, 'paid'),
    (1006, 6, '2026-01-01', 8500.00, 'paid'),
    (1007, 7, '2026-01-01', 3500.00, 'paid'),
    (1008, 8, '2026-01-01', 12000.00, 'paid'),
    (1009, 9, '2026-01-01', 5500.00, 'paid'),
    (1010, 10, '2026-01-01', 150.00, 'paid'),
    (1011, 1, '2026-02-01', 4500.00, 'paid'),
    (1012, 2, '2026-02-01', 3200.00, 'paid'),
    (1013, 5, '2026-02-01', 6000.00, 'paid'),
    (1014, 6, '2026-02-01', 8500.00, 'paid'),
    (1015, 8, '2026-02-01', 12000.00, 'paid');
    """)

    # Seed MRR Movements
    con.execute("""
    DELETE FROM mrr_movements;
    INSERT INTO mrr_movements VALUES
    (1, 1, '2026-01', 4500.00, 0.00, 0.00, 0.00),
    (2, 2, '2026-01', 3200.00, 0.00, 0.00, 0.00),
    (3, 5, '2026-01', 5000.00, 1000.00, 0.00, 0.00),
    (4, 6, '2026-01', 8500.00, 0.00, 0.00, 0.00),
    (5, 8, '2026-01', 10000.00, 2000.00, 0.00, 0.00),
    (6, 11, '2026-01', 0.00, 0.00, 0.00, 120.00);
    """)

    con.close()

    # 2. Write Config, Rules, and Metrics
    import yaml
    from vero.config import VeroConfig
    cfg = VeroConfig()
    cfg.database.dialect = "duckdb"
    cfg.database.connection_string = f"duckdb:///{db_file.resolve()}"
    cfg.storage.backend = "local"
    cfg.auth.mode = "local"
    
    config_file = context_dir / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(cfg.model_dump(), f, default_flow_style=False, sort_keys=False)

    # Write RULES.md
    (context_dir / "RULES.md").write_text(DEMO_RULES, encoding="utf-8")

    # Write metrics.yaml
    (context_dir / "metrics.yaml").write_text(DEMO_METRICS, encoding="utf-8")

    # 3. Introspect and sync schemas
    from vero.db import DatabaseManager
    from vero.context import ContextEngine
    db = DatabaseManager(dialect="duckdb", connection_string=f"duckdb:///{db_file.resolve()}")
    schema_info = db.introspect_schema()
    engine = ContextEngine()
    engine.sync_schemas(schema_info, domain="global")

    return db_file
