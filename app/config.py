from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (and `.env` locally)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LeadPilot"
    database_url: str = "sqlite:///./leadpilot.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
