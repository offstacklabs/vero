import os
from pathlib import Path
from typing import Optional, Dict, Any
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

class CostGuardConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enforce pre-execution dry-run cost estimation and byte limit checks")
    max_bytes_scanned: int = Field(default=10 * 1024 * 1024 * 1024, description="Maximum bytes allowed per query before blocking (default: 10 GB)")
    cost_per_tb_usd: float = Field(default=6.25, description="Cost in USD per Terabyte scanned (default: $6.25 for BigQuery on-demand)")

class VeroConfig(BaseModel):
    version: str = "1.0"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    cost_guard: CostGuardConfig = Field(default_factory=CostGuardConfig)
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
