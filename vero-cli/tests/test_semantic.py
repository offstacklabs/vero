import pytest
from vero.semantic import LookMLParser, DbtSemanticParser, CubeSchemaParser, SemanticImporter
from vero.context import ContextEngine

def test_parse_lookml_measures():
    lookml_sample = """
    view: order_items {
      sql_table_name: public.order_items ;;

      dimension: id {
        primary_key: yes
        type: number
        sql: ${TABLE}.id ;;
      }

      measure: count {
        type: count
        description: "Total order item records"
      }

      measure: total_sale_price {
        type: sum
        sql: ${sale_price} ;;
        description: "Gross merchandise revenue"
      }

      measure: average_sale_price {
        type: average
        sql: ${sale_price} ;;
        description: "Average price per item"
      }

      measure: distinct_orders {
        type: count_distinct
        sql: ${order_id} ;;
      }
    }
    """

    metrics = LookMLParser.parse_content(lookml_sample, domain="finance")
    print(metrics)
    assert len(metrics) == 4

    metrics_by_name = {m.name: m for m in metrics}
    assert "count" in metrics_by_name
    assert metrics_by_name["count"].sql == "COUNT(*)"
    assert metrics_by_name["count"].domain == "finance"

    assert "total_sale_price" in metrics_by_name
    assert metrics_by_name["total_sale_price"].sql == "SUM(sale_price)"
    assert metrics_by_name["total_sale_price"].description == "Gross merchandise revenue"

    assert "average_sale_price" in metrics_by_name
    assert metrics_by_name["average_sale_price"].sql == "AVG(sale_price)"

    assert "distinct_orders" in metrics_by_name
    assert metrics_by_name["distinct_orders"].sql == "COUNT(DISTINCT order_id)"

def test_parse_dbt_semantic_models():
    dbt_manifest = {
        "semantic_models": {
            "semantic_model.my_project.orders": {
                "name": "orders",
                "node_relation": {"alias": "fct_orders"},
                "measures": [
                    {
                        "name": "order_total",
                        "agg": "sum",
                        "expr": "amount",
                        "description": "Sum of total order value"
                    },
                    {
                        "name": "customers_count",
                        "agg": "count_distinct",
                        "expr": "customer_id",
                        "description": "Unique purchasing customers"
                    }
                ]
            }
        },
        "metrics": {
            "metric.my_project.net_revenue": {
                "name": "net_revenue",
                "type": "simple",
                "type_params": {"measure": "order_total"},
                "description": "Net revenue from orders"
            }
        }
    }

    metrics = DbtSemanticParser.parse_manifest(dbt_manifest, domain="marketing")
    assert len(metrics) == 3

    m_map = {m.name: m for m in metrics}
    assert m_map["order_total"].sql == "SUM(amount)"
    assert m_map["order_total"].source_table == "fct_orders"
    assert m_map["customers_count"].sql == "COUNT(DISTINCT customer_id)"
    assert m_map["net_revenue"].name == "net_revenue"

def test_parse_cube_schema():
    cube_yaml = """
    cubes:
      - name: line_items
        sql_table: analytics.line_items
        measures:
          - name: count
            type: count
            description: "Total line items"
          - name: total_revenue
            type: sum
            sql: price * quantity
            description: "Gross revenue"
    """

    metrics = CubeSchemaParser.parse_content(cube_yaml, domain="sales")
    assert len(metrics) == 2

    m_map = {m.name: m for m in metrics}
    assert "line_items_count" in m_map
    assert m_map["line_items_count"].sql == "COUNT(*)"
    assert "line_items_total_revenue" in m_map
    assert m_map["line_items_total_revenue"].sql == "SUM(price * quantity)"
    assert m_map["line_items_total_revenue"].source_table == "analytics.line_items"

def test_semantic_importer_sync_to_vero():
    engine = ContextEngine()
    importer = SemanticImporter(context_engine=engine)

    lookml_sample = """
    view: churn {
      measure: churn_rate {
        type: number
        sql: SUM(lost_users) / NULLIF(SUM(total_users), 0) ;;
        description: "Customer churn percentage"
      }
    }
    """

    metrics = importer.import_lookml(lookml_sample, domain="product")
    count = importer.sync_to_vero(metrics, domain="product")
    assert count == 1

    stored = engine.get_metrics(domain="product")
    assert any(m["name"] == "churn_rate" for m in stored)

def test_parse_apache_ossie_schema():
    from vero.semantic import OssieSemanticParser
    
    ossie_yaml = """
    version: "0.2.0.dev0"
    name: retail_sales_model
    description: "Retail sales semantic model"

    datasets:
      - name: customers
        source: analytics.dim_customers
        fields:
          - name: customer_id
            datatype: Integer
          - name: country
            datatype: String
            dimension:
              is_time: false
      - name: orders
        source: analytics.fct_orders
        fields:
          - name: order_date
            datatype: Date
            dimension:
              is_time: true
          - name: amount
            datatype: Decimal

    metrics:
      - name: total_revenue
        description: "Gross customer spend"
        datatype: Decimal
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: "SUM(orders.amount)"
            - dialect: SNOWFLAKE
              expression: "SUM(orders.amount::FLOAT)"
        ai_context:
          synonyms:
            - "gross sales"
            - "turnover"

      - name: avg_order_value
        description: "Average revenue per order"
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: "AVG(orders.amount)"
    """

    # 1. Parse with target dialect = snowflake
    metrics_sf = OssieSemanticParser.parse_content(ossie_yaml, domain="finance", target_dialect="snowflake")
    assert len(metrics_sf) == 2

    m_map_sf = {m.name: m for m in metrics_sf}
    assert m_map_sf["total_revenue"].sql == "SUM(orders.amount::FLOAT)"
    assert "gross sales" in m_map_sf["total_revenue"].description
    assert "country" in m_map_sf["total_revenue"].dimensions
    assert "order_date" in m_map_sf["total_revenue"].dimensions

    # 2. Parse with default ANSI_SQL fallback
    metrics_ansi = OssieSemanticParser.parse_content(ossie_yaml, domain="finance")
    m_map_ansi = {m.name: m for m in metrics_ansi}
    assert m_map_ansi["total_revenue"].sql == "SUM(orders.amount)"
    assert m_map_ansi["avg_order_value"].sql == "AVG(orders.amount)"

