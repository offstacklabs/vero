import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
from sqlalchemy import create_engine, text

class SemanticCacheEngine:
    """
    Intelligent Query Caching Layer (Cube.js Killer).
    Uses local SQLite to store query AST hashes and their result payloads.
    Intercepts identical queries within the TTL window to return instant results ($0 warehouse cost).
    """

    def __init__(self, db_path: Optional[str] = None):
        from vero.config import VeroConfig
        self.cfg = VeroConfig.load().cache
        
        if not db_path:
            root = VeroConfig.get_workspace_root()
            db_path = str(root / ".vero" / "semantic_cache.db")
            
        self.engine = create_engine(f"sqlite:///{db_path}")
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        with self.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS _vero_semantic_cache (
                    query_hash VARCHAR(64) PRIMARY KEY,
                    sql TEXT NOT NULL,
                    dialect VARCHAR(32) NOT NULL,
                    result_json TEXT NOT NULL,
                    bytes_scanned BIGINT DEFAULT 0,
                    cost_usd FLOAT DEFAULT 0.0,
                    created_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL
                )
            """))

    def _hash_query(self, sql: str, dialect: str) -> str:
        """Deterministically hash the SQL string (ignoring formatting/case)."""
        normalized = " ".join(sql.strip().lower().split())
        return hashlib.sha256(f"{dialect}:{normalized}".encode("utf-8")).hexdigest()

    def get_cached_result(self, sql: str, dialect: str) -> Optional[Dict[str, Any]]:
        """Returns the cached query result if it exists and is not expired."""
        if not self.cfg or not self.cfg.enabled:
            return None

        q_hash = self._hash_query(sql, dialect)
        now = datetime.now(timezone.utc)

        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT result_json, bytes_scanned, cost_usd FROM _vero_semantic_cache WHERE query_hash = :h AND expires_at > :now"),
                {"h": q_hash, "now": now}
            ).fetchone()

            if row:
                try:
                    payload = json.loads(row[0])
                    # Inject cache metadata
                    payload["cache_hit"] = True
                    payload["original_bytes_scanned"] = row[1]
                    payload["original_cost_usd"] = row[2]
                    payload["duration_ms"] = 0.0 # Instant return
                    return payload
                except Exception:
                    return None

        return None

    def set_cached_result(
        self, 
        sql: str, 
        dialect: str, 
        result: Dict[str, Any], 
        bytes_scanned: int = 0, 
        cost_usd: float = 0.0
    ) -> None:
        """Stores a successful query execution in the cache."""
        if not self.cfg or not self.cfg.enabled:
            return

        q_hash = self._hash_query(sql, dialect)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.cfg.ttl_seconds)

        # Strip cache metadata if accidentally passed
        store_payload = {k: v for k, v in result.items() if k not in ["cache_hit", "original_bytes_scanned", "original_cost_usd"]}

        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                    INSERT INTO _vero_semantic_cache (query_hash, sql, dialect, result_json, bytes_scanned, cost_usd, created_at, expires_at)
                    VALUES (:h, :s, :d, :r, :b, :c, :cat, :exp)
                    ON CONFLICT(query_hash) DO UPDATE SET 
                        result_json=excluded.result_json,
                        bytes_scanned=excluded.bytes_scanned,
                        cost_usd=excluded.cost_usd,
                        created_at=excluded.created_at,
                        expires_at=excluded.expires_at
                    """),
                    {
                        "h": q_hash,
                        "s": sql,
                        "d": dialect,
                        "r": json.dumps(store_payload),
                        "b": bytes_scanned,
                        "c": cost_usd,
                        "cat": now,
                        "exp": expires
                    }
                )
        except Exception:
            pass # Fail gracefully if cache write fails
