"""Centralised, typed access to runtime configuration.

All values come from environment variables (loaded via `op run` in production
or `python-dotenv` for local dev). Never hardcode secrets here.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env_once() -> None:
    """Load .env.local if present, but skip op:// references.

    `.env.local` exists for two purposes: (1) hold non-secret config the same
    way `.env.template` does, and (2) document op:// references that get
    resolved at process start by `op run --account my.1password.com --env-file=.env.local -- <cmd>`.

    If a Python process imports `ai_sector_watch.config` *without* having
    been invoked via `op run`, the values are still raw `op://` strings.
    Pushing those into `os.environ` is worse than leaving the variable
    unset, because downstream code (psycopg, the Anthropic SDK) will treat
    them as the actual secret and fail in confusing ways.

    Solution: parse the file ourselves with `dotenv_values` and only push
    values that are NOT op:// references into the environment. The op
    references are loaded by `op run` directly and never need to flow
    through this function.

    Idempotent: never overwrites a variable already set by the parent shell
    (so `op run` always wins).
    """
    env_local = REPO_ROOT / ".env.local"
    if not env_local.exists():
        return
    for key, value in dotenv_values(env_local).items():
        if value is None:
            continue
        if value.startswith("op://"):
            continue
        os.environ.setdefault(key, value)


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
