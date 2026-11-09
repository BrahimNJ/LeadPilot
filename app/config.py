from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (and `.env` locally)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LeadPilot"
    database_url: str = "sqlite:///./leadpilot.db"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Browser origins allowed to call the API, as a JSON list. Empty: no CORS headers.
    cors_origins: list[str] = []
    # Largest request body accepted, in bytes.
    max_body_bytes: int = 1_048_576
    # Fill an empty database with sample records at startup (public demo).
    seed_demo: bool = False

    # Without a key the copilot runs on transparent offline rules.
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"


@lru_cache
def get_settings() -> Settings:
    return Settings()
