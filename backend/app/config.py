"""Settings and the entity-resolution policies.

The policies live in config rather than in code because they are business
decisions that will change, and changing one should not require a code diff.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute, so the app finds its settings whether it is launched from
# backend/ (uvicorn) or from the repo root (the Vercel entry point).
# On Vercel there is no .env at all -- the values come from the dashboard.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # Supabase -> Project Settings -> Database -> Connection string (URI).
    # Use the pooled connection string for an app server.
    database_url: str = ""

    # Which people source wins when two files disagree about the same id.
    # Inert wherever they agree; only decides genuine conflicts.
    people_precedence: tuple[str, ...] = ("people.json", "people.yml")

    # collapse_to_lowest -> one id survives, the other's keys become aliases
    # quarantine         -> both flagged synthetic, neither deleted
    duplicate_policy: str = "collapse_to_lowest"

    max_upload_bytes: int = 32 * 1024 * 1024

    @property
    def sqlalchemy_url(self) -> str:
        # SQLAlchemy needs the psycopg2 driver named explicitly.
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return self.database_url


settings = Settings()
