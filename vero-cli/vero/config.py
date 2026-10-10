import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import yaml
from dotenv import load_dotenv

# Load .env file globally if present
load_dotenv()

class DatabaseConfig(BaseModel):
    dialect: str = Field(default="bigquery", description="Database dialect (bigquery, snowflake, postgres, duckdb)")
    connection_string: str = Field(default="bigquery://my-project-id/my_analytics_dataset", description="SQLAlchemy connection string")

class LLMConfig(BaseModel):
    model: str = Field(default="gpt-4o", description="LiteLLM model string (e.g. gpt-4o, claude-3-5-sonnet, ollama/llama3)")
    temperature: float = 0.0

class StorageConfig(BaseModel):
    backend: str = Field(default="local", description="Context storage backend: 'local' or 'database'")
    connection_string: Optional[str] = Field(default=None, description="SQLAlchemy connection string for centralized metadata DB (PostgreSQL, Supabase, etc.)")

class CostRatesConfig(BaseModel):
    bigquery_per_tb_usd: float = Field(default=6.25, description="Cost in USD per TB scanned for BigQuery on-demand")
    snowflake_credit_usd: float = Field(default=3.00, description="Cost in USD per Snowflake credit")
    snowflake_warehouse_size: str = Field(default="X-Small", description="Snowflake warehouse size: X-Small (1 credit/hr), Small (2), Medium (4), Large (8)")
    postgres_hourly_usd: float = Field(default=0.10, description="Estimated hourly compute cost in USD for Postgres/RDS instance")

class CostGuardConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enforce pre-execution dry-run cost estimation and byte limit checks")
    max_bytes_scanned: int = Field(default=10 * 1024 * 1024 * 1024, description="Maximum bytes allowed per query before blocking (default: 10 GB)")
    cost_per_tb_usd: float = Field(default=6.25, description="Cost in USD per Terabyte scanned (default: $6.25 for BigQuery on-demand)")
    rates: CostRatesConfig = Field(default_factory=CostRatesConfig)

class GovernanceConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable column-level data governance and PII masking")
    auto_detect_pii: bool = Field(default=True, description="Automatically mask emails, phones, SSNs, credit cards, and passwords")
    rules: List[Dict[str, str]] = Field(default_factory=list, description="Custom masking rules: [{'column': 'salary', 'strategy': 'REDACT'}]")

class OIDCConfig(BaseModel):
    provider_name: str = Field(default="Okta", description="Display name of enterprise identity provider (Okta, OneLogin, Azure AD, Google)")
    issuer_url: str = Field(default="", description="OIDC issuer URL (e.g. https://company.okta.com)")
    client_id: str = Field(default="", description="OIDC client ID")
    group_mapping: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "Data-Admins": {"role": "admin", "domains": ["*"]},
            "Finance-Team": {"role": "analyst", "domains": ["finance"]},
            "Marketing-Team": {"role": "analyst", "domains": ["marketing"]},
            "All-Employees": {"role": "viewer", "domains": ["global"]}
        },
        description="Maps corporate groups to Vero roles and domains"
    )

class AuthConfig(BaseModel):
    mode: str = Field(default="local", description="Auth mode: 'local' (zero-friction OSS) or 'oidc' (enterprise Okta/OneLogin SSO)")
    oidc: OIDCConfig = Field(default_factory=OIDCConfig)

class VeroConfig(BaseModel):
    version: str = "1.0"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    cost_guard: CostGuardConfig = Field(default_factory=CostGuardConfig)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    context_dir: str = ".vero"

    @classmethod
    def get_workspace_root(cls) -> Path:
        """Finds the workspace root by looking for .vero folder upwards."""
        current = Path.cwd()
        for parent in [current, *current.parents]:
            if (parent / ".vero").exists():
                return parent
        return Path.cwd() # fallback to current dir

    @classmethod
    def load(cls) -> "VeroConfig":
        root = cls.get_workspace_root()
        path = root / ".vero" / "config.yaml"
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return cls(**data)

    def save(self) -> None:
        root = self.get_workspace_root()
        path = root / self.context_dir / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)
