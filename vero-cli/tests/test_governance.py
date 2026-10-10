import pytest
from vero.governance import DataGovernanceEngine
from vero.db import DatabaseManager

def test_pii_masking_strategies():
    gov = DataGovernanceEngine(enabled=True, auto_detect_pii=True)

    # 1. Email masking
    masked_email = gov.apply_mask("alice.smith@enterprise.com", "PARTIAL_EMAIL")
    assert "@enterprise.com" in masked_email
    assert "alice.smith" not in masked_email
    assert masked_email.startswith("a***h@")

    # 2. Phone masking
    masked_phone = gov.apply_mask("+1-555-234-5678", "PARTIAL_PHONE")
    assert masked_phone == "***-***-5678"

    # 3. Card masking
    masked_card = gov.apply_mask("4111222233334444", "PARTIAL_CARD")
    assert masked_card == "**** **** **** 4444"

    # 4. Redaction
    assert gov.apply_mask("TopSecretPassword!", "REDACT") == "[REDACTED]"

    # 5. Pseudonymous Hashing
    hash_val = gov.apply_mask("user_12345", "HASH")
    assert len(hash_val) == 16
    # Same value produces deterministic hash for analytical joins
    assert gov.apply_mask("user_12345", "HASH") == hash_val
    assert gov.apply_mask("user_99999", "HASH") != hash_val

def test_auto_detect_dataset_masking():
    gov = DataGovernanceEngine(
        enabled=True,
        auto_detect_pii=True,
        custom_rules=[{"column": "salary", "strategy": "REDACT"}]
    )

    columns = ["id", "customer_name", "user_email", "phone_number", "salary"]
    rows = [
        [1, "Alice", "alice@example.com", "555-123-4567", 120000],
        [2, "Bob", "bob@example.com", "555-987-6543", 95000]
    ]

    masked_rows, masked_cols = gov.mask_dataset(columns, rows)

    assert set(masked_cols) == {"user_email", "phone_number", "salary"}
    # Non-sensitive columns unchanged
    assert masked_rows[0][0] == 1
    assert masked_rows[0][1] == "Alice"
    # Sensitive columns masked
    assert "@example.com" in masked_rows[0][2]
    assert masked_rows[0][2] != "alice@example.com"
    assert masked_rows[0][3] == "***-***-4567"
    assert masked_rows[0][4] == "[REDACTED]"

def test_database_manager_governance_integration():
    db = DatabaseManager(dialect="sqlite", connection_string="sqlite:///:memory:")
    con = db.get_engine()
    from sqlalchemy import text
    with con.connect() as conn:
        conn.execute(text("CREATE TABLE contacts (id INT, name TEXT, email TEXT, secret_token TEXT);"))
        conn.execute(text("INSERT INTO contacts VALUES (1, 'Alice', 'alice@test.com', 'tok_12345');"))
        conn.commit()

    result = db.execute_query("SELECT * FROM contacts", mask_pii=True)

    assert "email" in result["masked_columns"]
    assert "secret_token" in result["masked_columns"]
    assert result["rows"][0][1] == "Alice"
    assert result["rows"][0][2] != "alice@test.com"
    assert result["rows"][0][3] == "[REDACTED]"
