"""Tests for structured research brief generation."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from ai_sector_watch.research.briefs import (
    build_research_brief_run,
    research_run_to_dict,
    write_research_run_json,
)
from ai_sector_watch.sources.base import RawItem
from scripts.run_research_brief import previous_scheduled_run_date, research_window


def test_build_research_brief_run_shapes_primary_source_items() -> None:
    item = RawItem(
        source_slug="huggingface_papers",
        url="https://huggingface.co/papers/2604.01234",
        title="Reasoning agents for long context code tasks",
        summary="A paper about agent reasoning, benchmarks, and tool use.",
        published_at=datetime(2026, 5, 2, 3, tzinfo=UTC),
        raw={"arxiv_id": "2604.01234", "upvotes": 42},
    )

    run = build_research_brief_run(
        raw_items=[item],
        run_date=date(2026, 5, 2),
        window_start=datetime(2026, 5, 1, tzinfo=UTC),
        window_end=datetime(2026, 5, 3, tzinfo=UTC),
    )

    payload = research_run_to_dict(run)
    top_item = payload["sections"]["top_items"][0]
    assert payload["run_date"] == "2026-05-02"
    assert payload["status"] == "published"
    assert top_item["primary_url"] == "https://arxiv.org/abs/2604.01234"
    assert top_item["secondary_urls"] == ["https://huggingface.co/papers/2604.01234"]
    assert top_item["item_type"] == "benchmark"
    assert top_item["evidence_quality"]
    assert top_item["limitations"]


def test_write_research_run_json_round_trips(tmp_path) -> None:
    run = build_research_brief_run(
        raw_items=[],
        run_date=date(2026, 5, 2),
        window_start=datetime(2026, 5, 1, tzinfo=UTC),
        window_end=datetime(2026, 5, 3, tzinfo=UTC),
    )

    path = write_research_run_json(run, tmp_path)
    payload = json.loads(path.read_text())

    assert path.name == "2026-05-02.json"
    assert payload["sections"]["skipped_noise_note"]
    assert payload["sections"]["top_items"] == []


def test_research_window_for_australian_tuesday_covers_prior_friday_gap() -> None:
    start, end = research_window(
        run_date=date(2026, 5, 5),
        hours=36,
        scheduled_window=True,
        timezone_name="Australia/Sydney",
    )

    assert previous_scheduled_run_date(date(2026, 5, 5)) == date(2026, 5, 1)
    assert start == datetime(2026, 4, 30, 14, tzinfo=UTC)
    assert end == datetime(2026, 5, 5, 14, tzinfo=UTC)


def test_research_window_for_australian_friday_covers_prior_tuesday_gap() -> None:
    start, end = research_window(
        run_date=date(2026, 5, 8),
        hours=36,
        scheduled_window=True,
        timezone_name="Australia/Sydney",
    )

    assert previous_scheduled_run_date(date(2026, 5, 8)) == date(2026, 5, 5)
    assert start == datetime(2026, 5, 4, 14, tzinfo=UTC)
    assert end == datetime(2026, 5, 8, 14, tzinfo=UTC)


def test_research_window_preserves_legacy_hour_lookback() -> None:
    start, end = research_window(
        run_date=date(2026, 5, 2),
        hours=36,
        scheduled_window=False,
        timezone_name="Australia/Sydney",
    )

    assert start == datetime(2026, 5, 1, 12, tzinfo=UTC)
    assert end == datetime(2026, 5, 3, tzinfo=UTC)
