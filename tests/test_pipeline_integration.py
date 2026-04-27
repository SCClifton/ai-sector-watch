"""Integration tests for the weekly pipeline orchestrator.

The pipeline is exercised in two modes:
- Pure dry-run with stubbed sources, stubbed LLM, and write_to_db=False.
- Live-DB mode (auto-skipped without SUPABASE_DB_URL) using a real Supabase
  connection plus stubbed LLM.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ai_sector_watch.digest.generator import (
    DigestNewsRow,
    DigestStats,
    write_digest,
)
from ai_sector_watch.extraction.claude_client import (
    ClaudeClient,
    StructuredResponse,
)
from ai_sector_watch.extraction.schema import (
    CompanyClassification,
    CompanyMention,
    CompanyMentionList,
    CompanyValidation,
    NewsClassification,
)
from ai_sector_watch.pipeline.weekly import run_weekly_pipeline
from ai_sector_watch.sources.base import RawItem, SourceBase


class FakeSource(SourceBase):
    slug = "fake_source"
    kind = "news"

    def __init__(self, items: list[RawItem]) -> None:
        super().__init__()
        self._items = items

    def fetch(self, *, limit=None):
        return list(self._items[: limit if limit else None])


def _stub_client(tmp_path: Path) -> ClaudeClient:
    """Client whose `_dispatch` returns canned structured responses."""
    client = ClaudeClient(model="claude-sonnet-4-6", budget_usd=2.0, cache_dir=tmp_path)

    canned: dict[str, object] = {
        "CompanyMentionList": CompanyMentionList(
            mentions=[
                CompanyMention(
                    name="NewMarqo",
                    confidence=0.9,
                    is_anz=True,
                    city="Sydney",
                    country="AU",
                ),
                CompanyMention(
                    name="OpenAI",
                    confidence=0.99,
                    is_anz=False,
                    city="San Francisco",
                    country="US",
                ),
            ]
        ),
        "CompanyValidation": CompanyValidation(
            is_valid=True,
            is_ai_company=True,
            reasoning="It's a real Sydney AI company.",
            canonical_name=None,
        ),
        "CompanyClassification": CompanyClassification(
            sector_tags=["foundation_models"],
            stage="seed",
            summary="A new Sydney foundation-model lab.",
        ),
        "NewsClassification": NewsClassification(kind="funding", is_relevant=True),
    }

    def fake_dispatch(self, *, system, prompt, schema_cls, max_tokens):
        parsed = canned[schema_cls.__name__]
        cost = self._estimate_cost(input_tokens=10, output_tokens=20)
        return StructuredResponse(
            parsed=parsed,
            input_tokens=10,
            output_tokens=20,
            cost_usd=cost,
            cached=False,
        )

    client._dispatch = fake_dispatch.__get__(client, ClaudeClient)
    return client


# ----- Dry-run path (no DB) ------------------------------------------------


def test_pipeline_dry_run_extracts_without_db_writes(tmp_path) -> None:
    items = [
        RawItem(
            source_slug="fake_source",
            url="https://example.com/post/1",
            title="NewMarqo raises seed",
            summary="Sydney company NewMarqo raises seed for vector search.",
            published_at=datetime(2026, 4, 21, tzinfo=UTC),
        )
    ]
    result = run_weekly_pipeline(
        sources=[FakeSource(items)],
        client=_stub_client(tmp_path),
        items_per_source=10,
        write_to_db=False,
    )
    assert result.sources_attempted == 1
    assert result.sources_ok == 1
    assert result.items_seen == 1
    # No DB writes in dry-run.
    assert result.items_new == 0
    assert result.candidates_added == 0


def test_pipeline_dry_run_with_failing_source_continues() -> None:
    class Boom(SourceBase):
        slug = "boom"
        kind = "news"

        def fetch(self, *, limit=None):
            raise RuntimeError("simulated network failure")

    result = run_weekly_pipeline(
        sources=[Boom()],
        write_to_db=False,
    )
    assert result.sources_attempted == 1
    assert result.sources_ok == 0
    assert result.errors and "Boom" not in result.errors[0] and "boom" in result.errors[0]


# ----- Digest writer ------------------------------------------------------


def test_write_digest_renders_expected_sections(tmp_path) -> None:
    stats = DigestStats(
        sources_attempted=3,
        sources_ok=2,
        items_seen=10,
        items_new=4,
        candidates_added=1,
        cost_usd=0.0123,
    )
    news = [
        DigestNewsRow(
            title="Sample funding",
            url="https://example.com/x",
            source_slug="fake_source",
            kind="funding",
            company_names=["NewMarqo"],
        )
    ]
    path = write_digest(
        run_date=date(2026, 4, 27),
        stats=stats,
        new_companies=["NewMarqo"],
        news=news,
        output_dir=tmp_path,
    )
    text = path.read_text(encoding="utf-8")
    assert path.name == "2026-04-27.md"
    assert "Weekly digest, 2026-04-27" in text
    assert "Sources attempted: 3" in text
    assert "NewMarqo" in text
    assert "Sample funding" in text
    # PRD section 16: no em dashes in user-facing markdown.
    assert "—" not in text


def test_write_digest_handles_empty_run(tmp_path) -> None:
    stats = DigestStats(
        sources_attempted=0,
        sources_ok=0,
        items_seen=0,
        items_new=0,
        candidates_added=0,
        cost_usd=0.0,
    )
    path = write_digest(
        run_date=date(2026, 4, 27),
        stats=stats,
        new_companies=[],
        news=[],
        output_dir=tmp_path,
    )
    text = path.read_text(encoding="utf-8")
    assert "Sources attempted: 0" in text
    assert "## Relevant news" not in text


# ----- Live-DB path -------------------------------------------------------

pytestmark_live = pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL not set; skipping live integration",
)


@pytestmark_live
def test_pipeline_live_full_round_trip(tmp_path) -> None:
    """End-to-end: fake source + stub LLM, real Supabase. Cleans up after."""
    from ai_sector_watch.storage import supabase_db

    items = [
        RawItem(
            source_slug="fake_source",
            url="https://example.com/test/" + tmp_path.name,
            title="NewMarqo raises seed",
            summary="Sydney company NewMarqo raises seed.",
            published_at=datetime(2026, 4, 21, tzinfo=UTC),
        )
    ]
    result = run_weekly_pipeline(
        sources=[FakeSource(items)],
        client=_stub_client(tmp_path),
        items_per_source=10,
        write_to_db=True,
        digest_date=date(2026, 4, 27),
    )
    assert result.candidates_added >= 1
    assert result.items_new >= 1
    assert result.digest_path is not None
    # Cleanup.
    with supabase_db.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM news_items WHERE source_url = %s", (items[0].url,))
        cur.execute("DELETE FROM companies WHERE name_normalised = %s", ("newmarqo",))
        conn.commit()
