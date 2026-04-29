"""Tests for company rejection application."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import apply_company_rejections as apply_rejections  # noqa: E402


class FakeConn:
    """Minimal connection stub for rejection tests."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def _write_payload(path: Path, *, companies: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps({"companies": companies}), encoding="utf-8")


def test_dry_run_counts_only_rejection_verdicts(tmp_path: Path) -> None:
    path = tmp_path / "flags.json"
    _write_payload(
        path,
        companies=[
            {"id": "a", "name": "RejectMe", "verdict": "flag_for_rejection"},
            {"id": "b", "name": "ReviewMe", "verdict": "flag_for_review"},
            {"id": "c", "name": "AlsoReject", "verdict": "flag_for_rejection"},
        ],
    )

    summary = apply_rejections.run_apply(input_path=path, apply=False)

    assert summary.errors == []
    assert summary.candidates_seen == 2
    assert summary.skipped_non_rejection == 1
    assert summary.rejected == 0
    assert summary.rejected_ids == ["a", "c"]


def test_apply_refuses_unresolved_op_reference(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "flags.json"
    _write_payload(
        path,
        companies=[{"id": "a", "name": "RejectMe", "verdict": "flag_for_rejection"}],
    )
    monkeypatch.setenv("SUPABASE_DB_URL", "op://vault/item/field")

    summary = apply_rejections.run_apply(input_path=path, apply=True)

    assert summary.rejected == 0
    assert summary.errors == [
        "live apply requires resolved SUPABASE_DB_URL; run via op run with .env.local"
    ]


def test_apply_writes_rejections_and_audit_events(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "flags.json"
    _write_payload(
        path,
        companies=[
            {
                "id": "company-1",
                "name": "RejectMe",
                "verdict": "flag_for_rejection",
                "notes": "Defunct since 2024.",
                "evidence_urls": ["https://example.com/postmortem"],
            },
            {
                "id": "company-2",
                "name": "KeepMe",
                "verdict": "flag_for_review",
            },
        ],
    )
    fake_conn = FakeConn()
    status_calls: list[tuple[str, str]] = []
    event_calls: list[dict[str, Any]] = []
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example")

    @contextmanager
    def fake_connection():
        yield fake_conn

    def fake_set_status(conn, company_id, status):
        status_calls.append((company_id, status))

    def fake_insert_ingest(conn, **kwargs):
        event_calls.append(kwargs)
        return "fake-event-id"

    monkeypatch.setattr(apply_rejections.supabase_db, "connection", fake_connection)
    monkeypatch.setattr(apply_rejections.supabase_db, "apply_schema", lambda conn: None)
    monkeypatch.setattr(apply_rejections.supabase_db, "set_company_status", fake_set_status)
    monkeypatch.setattr(apply_rejections.supabase_db, "insert_ingest_event", fake_insert_ingest)

    summary = apply_rejections.run_apply(input_path=path, apply=True)

    assert summary.errors == []
    assert summary.rejected == 1
    assert summary.skipped_non_rejection == 1
    assert status_calls == [("company-1", "rejected")]
    assert fake_conn.commits == 1
    assert len(event_calls) == 1
    assert event_calls[0]["source_slug"] == apply_rejections.ADMIN_SOURCE
    assert event_calls[0]["kind"] == "rejection_apply"
    assert event_calls[0]["payload"]["company_id"] == "company-1"
    assert event_calls[0]["payload"]["notes"] == "Defunct since 2024."


def test_payload_rejects_missing_id(tmp_path: Path) -> None:
    path = tmp_path / "flags.json"
    _write_payload(
        path,
        companies=[{"name": "NoId", "verdict": "flag_for_rejection"}],
    )

    summary = apply_rejections.run_apply(input_path=path, apply=False)

    assert summary.errors
    assert "missing id" in summary.errors[0]
