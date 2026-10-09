import pytest
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
