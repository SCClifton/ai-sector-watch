"""Tests for dump_verified_companies --since filter."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dump_verified_companies as dump  # noqa: E402


def _row(name: str, verified_at: datetime | str | None) -> dict[str, object]:
    return {"id": f"id-{name}", "name": name, "profile_verified_at": verified_at}


def test_filter_since_keeps_old_and_unverified() -> None:
    cutoff = date(2026, 4, 1)
    rows = [
        _row("Fresh", datetime(2026, 4, 15, tzinfo=UTC)),
        _row("Stale", datetime(2026, 1, 5, tzinfo=UTC)),
        _row("NeverVerified", None),
        _row("ExactlyAtCutoff", datetime(2026, 4, 1, tzinfo=UTC)),
    ]

    kept = dump.filter_since(rows, cutoff)

    names = {r["name"] for r in kept}
    # Older-than-cutoff and null verified_at survive; on-or-after cutoff drops.
    assert names == {"Stale", "NeverVerified"}


def test_filter_since_handles_iso_string_and_naive_datetime() -> None:
    cutoff = date(2026, 4, 1)
    rows = [
        _row("StringIso", "2026-01-05T00:00:00+00:00"),
        _row("NaiveDatetime", datetime(2026, 1, 5)),  # no tzinfo, treated as UTC
        _row("FreshString", "2026-04-15T00:00:00+00:00"),
    ]

    kept = dump.filter_since(rows, cutoff)

    names = {r["name"] for r in kept}
    assert names == {"StringIso", "NaiveDatetime"}


def test_filter_since_returns_empty_when_all_are_fresh() -> None:
    cutoff = date(2026, 1, 1)
    rows = [_row("Fresh", datetime(2026, 6, 1, tzinfo=UTC))]

    assert dump.filter_since(rows, cutoff) == []
