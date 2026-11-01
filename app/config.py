from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "VoltClause"
    environment: str = "local"  # local | ci | production | test

    # LLM Settings
    primary_model: str = "gpt-4o-mini"
    fallback_model: str = "mock-cea-expert"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    llm_timeout_seconds: float = 15.0
    llm_max_retries: int = 2
    llm_retry_delay_seconds: float = 0.5

    # Storage & DB
    database_url: str = "postgresql://postgres:postgres@localhost:5432/voltclause"
    usage_log_file: str = "logs/llm_usage.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
