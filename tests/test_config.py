"""Tests for the config loader."""

from __future__ import annotations

from pathlib import Path

from ai_sector_watch.config import REPO_ROOT, Config, get_config


def test_repo_root_points_at_project_root() -> None:
    assert (REPO_ROOT / "pyproject.toml").exists()


def test_get_config_uses_defaults_when_env_unset(monkeypatch) -> None:
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_BUDGET_USD_PER_RUN",
        "SUPABASE_DB_URL",
        "ADMIN_PASSWORD",
        "PIPELINE_LOG_LEVEL",
        "DIGEST_OUTPUT_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    config = Config.from_env()
    assert config.anthropic_api_key is None
    assert config.anthropic_model == "claude-sonnet-4-6"
    assert config.anthropic_budget_usd_per_run == 2.0
    assert config.supabase_db_url is None
    assert config.admin_password is None
    assert config.pipeline_log_level == "INFO"
    assert config.digest_output_dir == REPO_ROOT / "data" / "digests"


def test_get_config_reads_overrides_from_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
    monkeypatch.setenv("ANTHROPIC_BUDGET_USD_PER_RUN", "0.5")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example")
    monkeypatch.setenv("ADMIN_PASSWORD", "open-sesame")
    monkeypatch.setenv("PIPELINE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path))
    config = get_config()
    assert config.anthropic_api_key == "sk-test"
    assert config.anthropic_model == "claude-opus-4-7"
    assert config.anthropic_budget_usd_per_run == 0.5
    assert config.supabase_db_url == "postgresql://example"
    assert config.admin_password == "open-sesame"
    assert config.pipeline_log_level == "DEBUG"
    assert config.digest_output_dir == tmp_path
