"""Centralised, typed access to runtime configuration.

All values come from environment variables (loaded via `op run` in production
or `python-dotenv` for local dev). Never hardcode secrets here.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env_once() -> None:
    """Load .env.local if present (no-op in CI, where env vars are set directly)."""
    env_local = REPO_ROOT / ".env.local"
    if env_local.exists():
        load_dotenv(env_local)


_load_env_once()


@dataclass(frozen=True)
class Config:
    """Application configuration snapshot."""

    anthropic_api_key: str | None
    anthropic_model: str
    anthropic_budget_usd_per_run: float
    supabase_db_url: str | None
    admin_password: str | None
    pipeline_log_level: str
    digest_output_dir: Path

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            anthropic_budget_usd_per_run=float(os.environ.get("ANTHROPIC_BUDGET_USD_PER_RUN", "2")),
            supabase_db_url=os.environ.get("SUPABASE_DB_URL"),
            admin_password=os.environ.get("ADMIN_PASSWORD"),
            pipeline_log_level=os.environ.get("PIPELINE_LOG_LEVEL", "INFO"),
            digest_output_dir=Path(
                os.environ.get("DIGEST_OUTPUT_DIR", str(REPO_ROOT / "data" / "digests"))
            ),
        )


def get_config() -> Config:
    return Config.from_env()


def configure_logging(level: str | None = None) -> None:
    """Configure structured-ish logging once at process start."""
    resolved = level or get_config().pipeline_log_level
    logging.basicConfig(
        level=resolved,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
