from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import yaml

class DatabaseConfig(BaseModel):
    dialect: str = Field(default="sqlite", description="Database dialect (sqlite, postgres, duckdb, snowflake, bigquery)")
    connection_string: str = Field(default="sqlite:///vero_sample.db", description="SQLAlchemy or DuckDB connection string")

class LLMConfig(BaseModel):
    model: str = Field(default="gpt-4o", description="LiteLLM model string (e.g. gpt-4o, claude-3-5-sonnet, ollama/llama3)")
    temperature: float = 0.0

class VeroConfig(BaseModel):
    version: str = "1.0"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    context_dir: str = ".vero"

    @classmethod
    def load(cls, path: Path = Path(".vero/config.yaml")) -> "VeroConfig":
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return cls(**data)

    def save(self, path: Path = Path(".vero/config.yaml")) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)
