import pytest
import time
from vero.cache import SemanticCacheEngine
from vero.config import VeroConfig

def test_semantic_cache_engine(tmp_path):
    db_path = tmp_path / "test_cache.db"
    cache = SemanticCacheEngine(db_path=str(db_path))

    # Mock the configuration to ensure it's enabled with short TTL
    cache.cfg.enabled = True
    cache.cfg.ttl_seconds = 2

    dialect = "bigquery"
    sql = "SELECT   * \n FROM  users  " # Messy formatting to test normalizer
    result_payload = {"columns": ["id"], "rows": [[1]], "row_count": 1}

    # 1. Miss
    assert cache.get_cached_result(sql, dialect) is None

    # 2. Set
    cache.set_cached_result(sql, dialect, result_payload, bytes_scanned=1048576, cost_usd=0.05)

    # 3. Hit (different formatting should resolve to same hash)
    hit = cache.get_cached_result("select * from users", dialect)
    assert hit is not None
    assert hit["cache_hit"] is True
    assert hit["original_bytes_scanned"] == 1048576
    assert hit["original_cost_usd"] == 0.05
    assert hit["rows"] == [[1]]
    assert hit["duration_ms"] == 0.0

    # 4. Expiration (wait for TTL)
    time.sleep(3)
    assert cache.get_cached_result(sql, dialect) is None
