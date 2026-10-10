import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from vero.server import app
from vero.storage import DatabaseContextStorage
from vero.context import ContextEngine

@pytest.fixture(autouse=True)
def isolate_test_storage(monkeypatch):
    test_storage = DatabaseContextStorage("sqlite:///:memory:")
    # Pre-populate dummy schema for annotation test
    test_storage.save_schema("customers", "# Table: customers\n| id | INT |")
    monkeypatch.setattr("vero.server.ContextEngine", lambda *args, **kwargs: ContextEngine(storage=test_storage))
    yield

def test_server_api_health():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "vero"}

def test_server_static_studio_mount():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "").lower()

def test_server_chat_stream_endpoint():
    from unittest.mock import patch, MagicMock
    with patch("vero.server.VeroAgent") as mock_agent_cls:
        mock_instance = MagicMock()
        mock_instance.ask_stream.return_value = [
            {"type": "stage", "stage": "retrieval", "message": "Grounding schemas..."},
            {"type": "complete", "result": {"question": "test", "data": None}}
        ]
        mock_agent_cls.return_value = mock_instance

        client = TestClient(app)
        response = client.post("/api/chat/stream", json={"question": "Show revenue"})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        content = response.text
        assert "Grounding schemas..." in content
        assert "complete" in content

def test_server_context_rules_endpoints():
    client = TestClient(app)
    # Save rules
    put_res = client.put("/api/rules", json={"rules": "- Always format currency in USD"})
    assert put_res.status_code == 200
    assert "Always format currency in USD" in put_res.json()["rules"]

    # Append rule ("Teach Vero")
    append_res = client.post("/api/rules/append", json={"rule": "Exclude internal accounts"})
    assert append_res.status_code == 200
    assert "Exclude internal accounts" in append_res.json()["rules"]

    # Get rules
    get_res = client.get("/api/rules")
    assert get_res.status_code == 200
    assert "Exclude internal accounts" in get_res.json()["rules"]

def test_server_context_metrics_endpoints():
    client = TestClient(app)
    # Create metric
    post_res = client.post("/api/metrics", json={
        "name": "nps_score",
        "description": "Net Promoter Score",
        "sql": "AVG(score)"
    })
    assert post_res.status_code == 200
    assert post_res.json()["metric"]["name"] == "nps_score"

    # Get metrics
    get_res = client.get("/api/metrics")
    assert get_res.status_code == 200
    metrics = [m["name"] for m in get_res.json()["metrics"]]
    assert "nps_score" in metrics

    # Delete metric
    del_res = client.delete("/api/metrics/nps_score")
    assert del_res.status_code == 200

def test_server_table_annotation_endpoint():
    client = TestClient(app)
    res = client.post("/api/schemas/customers/annotate", json={
        "annotation": "Verified primary customer model"
    })
    assert res.status_code == 200
    assert res.json()["table"] == "customers"

def test_server_domains_endpoints():
    client = TestClient(app)
    
    # 1. GET /api/domains
    domains_res = client.get("/api/domains")
    assert domains_res.status_code == 200
    domain_ids = [d["id"] for d in domains_res.json()["domains"]]
    assert "global" in domain_ids
    assert "finance" in domain_ids

    # 2. Domain-scoped rule save & get
    client.put("/api/rules", json={"rules": "- Recognized revenue GAAP", "domain": "finance"})
    rules_res = client.get("/api/rules?domain=finance")
    assert rules_res.status_code == 200
    assert "Recognized revenue GAAP" in rules_res.json()["rules"]

    # 3. Domain-scoped metric creation & filtering
    client.post("/api/metrics", json={
        "name": "roas",
        "description": "Return on Ad Spend",
        "sql": "revenue / ad_spend",
        "domain": "marketing"
    })
    
    mkt_metrics_res = client.get("/api/metrics?domain=marketing")
    assert mkt_metrics_res.status_code == 200
    mkt_metric_names = [m["name"] for m in mkt_metrics_res.json()["metrics"]]
    assert "roas" in mkt_metric_names

    fin_metrics_res = client.get("/api/metrics?domain=finance")
    assert fin_metrics_res.status_code == 200
    fin_metric_names = [m["name"] for m in fin_metrics_res.json()["metrics"]]
    assert "roas" not in fin_metric_names

def test_server_sessions_and_query_history():
    client = TestClient(app)

    # 1. Create a session
    sess_res = client.post("/api/sessions", json={"title": "Q3 Revenue Deep Dive", "domain": "finance"})
    assert sess_res.status_code == 200
    sess_id = sess_res.json()["id"]

    # 2. List sessions
    list_res = client.get("/api/sessions?domain=finance")
    assert list_res.status_code == 200
    assert any(s["id"] == sess_id for s in list_res.json()["sessions"])

    # 3. Save message and retrieve
    save_msg_res = client.post(f"/api/sessions/{sess_id}/messages", json={
        "sender": "assistant",
        "text": "Revenue increased by 14% this quarter.",
        "sql": "SELECT SUM(amount) FROM revenue"
    })
    assert save_msg_res.status_code == 200

    msgs_res = client.get(f"/api/sessions/{sess_id}/messages")
    assert msgs_res.status_code == 200
    assert len(msgs_res.json()["messages"]) == 1
    assert msgs_res.json()["messages"][0]["text"] == "Revenue increased by 14% this quarter."

    # 4. Query history logging
    with patch("vero.server.DatabaseManager") as mock_db_cls:
        mock_db = MagicMock()
        mock_db.execute_query.return_value = {"columns": ["num"], "rows": [[1]], "row_count": 1}
        mock_db_cls.return_value = mock_db

        q_res = client.post("/api/query", json={"sql": "SELECT 1 AS num"})
        assert q_res.status_code == 200

    hist_res = client.get("/api/history/queries")
    assert hist_res.status_code == 200
    assert len(hist_res.json()["runs"]) >= 1
    assert "SELECT 1 AS num" in hist_res.json()["runs"][0]["sql"]

    # 5. Delete session
    del_res = client.delete(f"/api/sessions/{sess_id}")
    assert del_res.status_code == 200

def test_server_dashboard_tiles():
    client = TestClient(app)

    # 1. Pin a KPI tile
    pin_res = client.post("/api/dashboard/tiles", json={
        "title": "Quarterly Revenue",
        "tile_type": "kpi",
        "sql": "SELECT SUM(amount) FROM orders",
        "domain": "finance",
        "data": {"columns": ["revenue"], "rows": [["$1.2M"]]}
    })
    assert pin_res.status_code == 200
    tile = pin_res.json()["tile"]
    tile_id = tile["id"]

    # 2. Get dashboard tiles
    tiles_res = client.get("/api/dashboard/tiles?domain=finance")
    assert tiles_res.status_code == 200
    assert any(t["id"] == tile_id for t in tiles_res.json()["tiles"])

    # 3. Unpin tile
    unpin_res = client.delete(f"/api/dashboard/tiles/{tile_id}")
    assert unpin_res.status_code == 200

def test_server_estimate_query():
    client = TestClient(app)
    with patch("vero.server.DatabaseManager") as mock_db_cls:
        mock_db = MagicMock()
        mock_db.estimate_query_cost.return_value = {
            "valid": True,
            "dialect": "bigquery",
            "bytes_scanned": 104857600,
            "bytes_formatted": "100.0 MB",
            "cost_usd": 0.0006,
            "cost_guard_passed": True
        }
        mock_db_cls.return_value = mock_db

        res = client.post("/api/query/estimate", json={"sql": "SELECT * FROM dataset.table"})
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["bytes_formatted"] == "100.0 MB"
        assert data["cost_guard_passed"] is True

def test_server_observability_stats():
    client = TestClient(app)
    res = client.get("/api/observability/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_queries" in data
    assert "total_tokens" in data
    assert "total_spend_usd" in data
    assert "llm_spend_usd" in data
    assert "warehouse_spend_usd" in data
    assert "cost_guard_savings_usd" in data
    assert "avg_latency_ms" in data
    assert "active_dialect" in data
    assert "top_expensive_queries" in data
    assert "daily_breakdown" in data
