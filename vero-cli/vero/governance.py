import re
import hashlib
from typing import List, Dict, Any, Tuple, Optional

class DataGovernanceEngine:
    """
    Enterprise Data Governance & PII Masking Engine.
    Detects sensitive columns and applies configurable masking strategies
    (REDACT, HASH/SHA256, PARTIAL_EMAIL, PARTIAL_PHONE, PARTIAL_CARD)
    before query data reaches the client or LLM context.
    """

    # Common PII column patterns mapped to default masking strategies
    DEFAULT_PII_RULES = [
        (r".*(?:password|secret|token|api_key).*", "REDACT"),
        (r".*(?:ssn|social_security|national_id).*", "REDACT"),
        (r".*(?:email|mail_address).*", "PARTIAL_EMAIL"),
        (r".*(?:phone|mobile|cell|telephone).*", "PARTIAL_PHONE"),
        (r".*(?:card_num|credit_card|card_number|pan|cvv|cvc).*", "PARTIAL_CARD"),
    ]

    def __init__(
        self,
        enabled: bool = True,
        auto_detect_pii: bool = True,
        custom_rules: Optional[List[Dict[str, str]]] = None
    ):
        self.enabled = enabled
        self.auto_detect_pii = auto_detect_pii
        self.custom_rules = custom_rules or []

    def get_strategy_for_column(self, col_name: str) -> Optional[str]:
        """Resolves the masking strategy for a column name."""
        col_lower = col_name.lower().strip()

        # 1. Explicit user-configured custom rules take precedence
        for rule in self.custom_rules:
            pattern = rule.get("column", "").lower().strip()
            if pattern == col_lower or re.match(f"^{pattern}$", col_lower):
                return rule.get("strategy", "REDACT").upper()

        # 2. Automated PII detection
        if self.auto_detect_pii:
            for pattern, strategy in self.DEFAULT_PII_RULES:
                if re.match(pattern, col_lower):
                    return strategy

        return None

    def apply_mask(self, value: Any, strategy: str) -> Any:
        """Applies masking strategy to an individual cell value."""
        if value is None:
            return None

        val_str = str(value).strip()
        if not val_str:
            return val_str

        strategy = strategy.upper()

        if strategy == "REDACT":
            return "[REDACTED]"

        elif strategy in ["HASH", "SHA256"]:
            return hashlib.sha256(val_str.encode("utf-8")).hexdigest()[:16]

        elif strategy == "PARTIAL_EMAIL":
            if "@" in val_str:
                user, domain = val_str.split("@", 1)
                if len(user) <= 2:
                    masked_user = user[0] + "***"
                else:
                    masked_user = user[0] + "***" + user[-1]
                return f"{masked_user}@{domain}"
            return "[REDACTED_EMAIL]"

        elif strategy == "PARTIAL_PHONE":
            # Keep last 4 digits
            digits = re.sub(r"\D", "", val_str)
            if len(digits) >= 4:
                return f"***-***-{digits[-4:]}"
            return "***-***-****"

        elif strategy == "PARTIAL_CARD":
            digits = re.sub(r"\D", "", val_str)
            if len(digits) >= 4:
                return f"**** **** **** {digits[-4:]}"
            return "**** **** **** ****"

        elif strategy == "NULL":
            return None

        return "[REDACTED]"

    def mask_dataset(
        self,
        columns: List[str],
        rows: List[List[Any]]
    ) -> Tuple[List[List[Any]], List[str]]:
        """
        Masks sensitive values in a result set and returns (masked_rows, masked_columns).
        """
        if not self.enabled or not rows:
            return rows, []

        col_strategies: Dict[int, str] = {}
        masked_column_names: List[str] = []

        for idx, col in enumerate(columns):
            strategy = self.get_strategy_for_column(col)
            if strategy:
                col_strategies[idx] = strategy
                masked_column_names.append(col)

        if not col_strategies:
            return rows, []

        masked_rows = []
        for row in rows:
            new_row = list(row)
            for col_idx, strategy in col_strategies.items():
                if col_idx < len(new_row):
                    new_row[col_idx] = self.apply_mask(new_row[col_idx], strategy)
            masked_rows.append(new_row)

        return masked_rows, masked_column_names
