"""Application settings.

Values come from environment variables, falling back to a `.env` file in the
current working directory. The same `.env` is read by systemd (EnvironmentFile=)
and by the cron job, so there is exactly one place to configure the app.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host:port/dbname
    database_url: str
    # Public address users reach the app at (through Nginx). Used to build share links.
    base_url: str = "http://localhost:8080"


@lru_cache
def get_settings() -> Settings:
    """Read settings once and reuse them (cached)."""
    return Settings()
