"""Tests for reviewed company profile update application."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import apply_company_profile_updates as apply_updates  # noqa: E402


class FakeConn:
    """Minimal connection stub for apply tests."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def _write_payload(path: Path, *, updates: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(
            {
                "companies": [
                    {
                        "id": "company-1",
                        "name": "Target",
                        "discovery_status": "verified",
                        "updates": updates,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_dry_run_counts_fields_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "updates.json"
    _write_payload(path, updates={"headcount_estimate": 50, "profile_sources": ["https://x"]})

    summary = apply_updates.run_apply(input_path=path, apply=False)

    assert summary.errors == []
    assert summary.companies_seen == 1
    assert summary.companies_updated == 0
    assert summary.fields_updated == 2


def test_apply_refuses_unresolved_op_reference(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "updates.json"
    _write_payload(path, updates={"headcount_estimate": 50})
    monkeypatch.setenv("SUPABASE_DB_URL", "op://vault/item/field")

    summary = apply_updates.run_apply(input_path=path, apply=True)

    assert summary.companies_updated == 0
    assert summary.errors == [
        "live apply requires resolved SUPABASE_DB_URL; run via op run with .env.local"
    ]


def test_apply_writes_reviewed_updates(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "updates.json"
    _write_payload(path, updates={"headcount_estimate": 50})
    fake_conn = FakeConn()
    captured: list[dict[str, Any]] = []
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example")

    @contextmanager
    def fake_connection():
        yield fake_conn

    def fake_update(conn, company_id, *, updates, enriched_at):
        captured.append({"company_id": company_id, "updates": updates, "enriched_at": enriched_at})

    monkeypatch.setattr(apply_updates.supabase_db, "connection", fake_connection)
    monkeypatch.setattr(apply_updates.supabase_db, "apply_schema", lambda conn: None)
    monkeypatch.setattr(apply_updates.supabase_db, "update_company_enrichment", fake_update)

    summary = apply_updates.run_apply(input_path=path, apply=True)

    assert summary.errors == []
    assert summary.companies_updated == 1
    assert fake_conn.commits == 1
    assert captured[0]["company_id"] == "company-1"
    assert captured[0]["updates"]["headcount_estimate"] == 50
    assert "profile_verified_at" in captured[0]["updates"]


def test_payload_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "updates.json"
    _write_payload(path, updates={"discovery_status": "verified"})

    summary = apply_updates.run_apply(input_path=path, apply=False)

    assert summary.errors
    assert "unsupported fields" in summary.errors[0]
