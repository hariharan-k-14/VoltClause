from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "examate-rag"
    environment: str = "local"  # local | ci | production
    database_url: str = ""
    llm_provider: str = "fake"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "examate-fake"
    llm_fallback_model: str = ""
    llm_fallback_base_url: str = ""
    llm_fallback_api_key: str = ""
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 3
    price_input_per_million: float = 0.0
    price_output_per_million: float = 0.0
    cost_log_path: str = "logs/cost.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
