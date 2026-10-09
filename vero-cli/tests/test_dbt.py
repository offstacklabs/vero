import pytest
import json
from pathlib import Path
from vero.dbt import DbtSyncEngine
from vero.context import ContextEngine

def test_dbt_manifest_sync(tmp_path: Path):
    # 1. Create a mock dbt manifest.json
    mock_manifest = {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.jaffle_shop.customers": {
                "resource_type": "model",
                "name": "customers",
                "description": "One record per customer with lifetime value",
                "columns": {
                    "customer_id": {
                        "name": "customer_id",
                        "data_type": "INTEGER",
                        "description": "Primary key of customer"
                    },
                    "lifetime_value": {
                        "name": "lifetime_value",
                        "data_type": "NUMERIC",
                        "description": "Total completed order amount"
                    }
                }
            },
            "model.jaffle_shop.orders": {
                "resource_type": "model",
                "name": "orders",
                "description": "One record per order",
                "columns": {
                    "order_id": {"name": "order_id", "data_type": "INTEGER"},
                    "customer_id": {"name": "customer_id", "data_type": "INTEGER"}
                }
            },
            "test.jaffle_shop.relationships_orders_customer_id": {
                "resource_type": "test",
                "test_metadata": {
                    "name": "relationships",
                    "kwargs": {
                        "field": "customer_id",
                        "to": "ref('customers')",
                        "to_field": "customer_id"
                    }
                },
                "depends_on": {
                    "nodes": ["model.jaffle_shop.orders", "model.jaffle_shop.customers"]
                }
            }
        },
        "metrics": {
            "metric.jaffle_shop.monthly_revenue": {
                "name": "monthly_revenue",
                "description": "Total monthly revenue",
                "type": "simple",
                "calculation_method": "SUM(lifetime_value)"
            }
        }
    }

    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(mock_manifest), encoding="utf-8")

    # 2. Run dbt sync with temporary context
    context = ContextEngine(context_dir=tmp_path / ".vero")
    sync_engine = DbtSyncEngine(context_engine=context)
    result = sync_engine.sync(manifest_file)

    # 3. Assertions
    assert result["models_synced"] == 2
    assert result["metrics_synced"] == 1
    assert "customers" in result["models"]
    assert "orders" in result["models"]

    # Verify generated schema file
    customers_md = (tmp_path / ".vero" / "schemas" / "customers.md").read_text()
    assert "One record per customer with lifetime value" in customers_md
    assert "customer_id" in customers_md
    assert "lifetime_value" in customers_md

    orders_md = (tmp_path / ".vero" / "schemas" / "orders.md").read_text()
    assert "customer_id" in orders_md
    assert "customers(customer_id)" in orders_md  # verified foreign key extraction

    # Verify generated metrics.yaml
    metrics_yaml = (tmp_path / ".vero" / "metrics.yaml").read_text()
    assert "monthly_revenue" in metrics_yaml
    assert "SUM(lifetime_value)" in metrics_yaml
