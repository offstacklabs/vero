import pytest
from vero.db import DatabaseManager

def test_safe_queries():
    db = DatabaseManager("sqlite", "sqlite:///:memory:")
    
    # Safe queries
    assert db.is_safe_query("SELECT * FROM users") is True
    assert db.is_safe_query("WITH cte AS (SELECT 1) SELECT * FROM cte") is True
    
    # Unsafe queries
    assert db.is_safe_query("DROP TABLE users") is False
    assert db.is_safe_query("DELETE FROM users WHERE id = 1") is False
    assert db.is_safe_query("UPDATE users SET name = 'admin'") is False
    assert db.is_safe_query("INSERT INTO users (id) VALUES (1)") is False
    
    # Injection/Stacking
    assert db.is_safe_query("SELECT * FROM users; DROP TABLE users") is False
    assert db.is_safe_query("WITH cte AS (DELETE FROM users RETURNING *) SELECT * FROM cte") is False

def test_execute_blocked():
    db = DatabaseManager("sqlite", "sqlite:///:memory:")
    with pytest.raises(ValueError, match="Query rejected"):
        db.execute_query("DROP TABLE users")
