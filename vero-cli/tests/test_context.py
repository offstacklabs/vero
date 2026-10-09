import pytest
from vero.context import ContextEngine

def test_in_memory_context_injection():
    engine = ContextEngine(
        rules="Always filter by status = 'active'.",
        metrics=[{
            "name": "mrr",
            "description": "Monthly Recurring Revenue",
            "sql": "SUM(mrr_amount)"
        }],
        schemas={
            "users": "# Table: users\n| id | INT |\n| status | VARCHAR |",
            "payments": "# Table: payments\n| id | INT |\n| mrr_amount | NUMERIC |"
        }
    )

    prompt = engine.get_full_context_prompt(query_hint="mrr payments")

    assert "Always filter by status = 'active'" in prompt
    assert "mrr" in prompt
    assert "SUM(mrr_amount)" in prompt
    assert "payments" in prompt
    assert "users" in prompt
