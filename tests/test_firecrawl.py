"""Tests for the Firecrawl enrichment client.

All tests stub `FirecrawlClient._dispatch()` so the live SDK is never
invoked. We mock the SDK shape rather than `httpx` because the SDK
abstracts the HTTP layer for us; reaching into httpx would be fragile.
"""

from __future__ import annotations

import json

import pytest

from ai_sector_watch.extraction.firecrawl_client import (
    DEFAULT_CREDITS_PER_CALL,
    FirecrawlBudgetExceeded,
    FirecrawlClient,
    _post_process,
    _sanitise,
    firecrawl_enrich,
)
from ai_sector_watch.extraction.schema import CompanyFacts


def _make_client(tmp_path, *, budget_credits: int = 200) -> FirecrawlClient:
    return FirecrawlClient(budget_credits=budget_credits, cache_dir=tmp_path)


SAMPLE_PAYLOAD: dict = {
    "founded_year": 2020,
    "description": "Relevance AI is an agent platform for the enterprise.",
    "founders": ["Daniel Vassilev", "Jacky Koh"],
    "city": "Sydney",
    "country": "AU",
    "sector_keywords": ["agents", "vector search", "RAG"],
    "last_funding_summary": "Series B led by Bessemer in 2024.",
    "confidence": 1.0,
}


def test_scrape_facts_returns_validated_company_facts(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)
    calls: list[str] = []

    def fake_dispatch(self, *, url, schema):
        calls.append(url)
        return dict(SAMPLE_PAYLOAD)

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    result = client.scrape_facts("https://relevanceai.com")
    assert calls == ["https://relevanceai.com"]
    assert isinstance(result.facts, CompanyFacts)
    assert result.facts.founded_year == 2020
    assert result.facts.founders == ["Daniel Vassilev", "Jacky Koh"]
    assert result.facts.confidence == 1.0
    assert result.cached is False
    assert result.credits_used == DEFAULT_CREDITS_PER_CALL
    assert client.stats.calls == 1
    assert client.stats.credits_used == DEFAULT_CREDITS_PER_CALL


def test_scrape_facts_caches_on_second_call(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)
    calls = {"count": 0}

    def fake_dispatch(self, *, url, schema):
        calls["count"] += 1
        return dict(SAMPLE_PAYLOAD)

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    a = client.scrape_facts("https://example.com")
    b = client.scrape_facts("https://example.com")
    assert calls["count"] == 1
    assert a.cached is False
    assert b.cached is True
    assert client.stats.cache_hits == 1
    # Cached call must NOT consume more budget.
    assert client.stats.credits_used == DEFAULT_CREDITS_PER_CALL


def test_budget_cap_blocks_further_scrapes(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path, budget_credits=DEFAULT_CREDITS_PER_CALL - 1)

    def fake_dispatch(self, *, url, schema):
        return dict(SAMPLE_PAYLOAD)

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    with pytest.raises(FirecrawlBudgetExceeded):
        client.scrape_facts("https://example.com")
    assert client.stats.calls == 0


def test_budget_cap_lets_first_call_through_then_blocks(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path, budget_credits=DEFAULT_CREDITS_PER_CALL)

    def fake_dispatch(self, *, url, schema):
        return dict(SAMPLE_PAYLOAD)

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    client.scrape_facts("https://a.com")
    with pytest.raises(FirecrawlBudgetExceeded):
        client.scrape_facts("https://b.com")


def test_scrape_failure_returns_empty_facts(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)

    def boom(self, *, url, schema):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(FirecrawlClient, "_dispatch", boom)

    result = client.scrape_facts("https://example.com")
    assert result.facts.confidence == 0.0
    assert result.facts.description is None
    assert result.credits_used == 0
    assert client.stats.calls == 1
    assert client.stats.failures and "network exploded" in client.stats.failures[0]


def test_em_dashes_in_description_are_sanitised(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)
    payload = dict(SAMPLE_PAYLOAD)
    payload["description"] = "Relevance AI is the agent platform — for the enterprise."
    payload["last_funding_summary"] = "Series B – Bessemer led, 2024."

    def fake_dispatch(self, *, url, schema):
        return payload

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    facts = client.scrape_facts("https://example.com").facts
    assert facts.description is not None
    assert "—" not in facts.description
    assert "–" not in facts.description
    assert facts.last_funding_summary is not None
    assert "—" not in facts.last_funding_summary
    assert "–" not in facts.last_funding_summary


def test_string_founded_year_coerced(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)
    payload = dict(SAMPLE_PAYLOAD)
    payload["founded_year"] = "2019"

    def fake_dispatch(self, *, url, schema):
        return payload

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    facts = client.scrape_facts("https://example.com").facts
    assert facts.founded_year == 2019


def test_string_list_field_coerced_to_list(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)
    payload = dict(SAMPLE_PAYLOAD)
    payload["founders"] = "Solo Founder"

    def fake_dispatch(self, *, url, schema):
        return payload

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    facts = client.scrape_facts("https://example.com").facts
    assert facts.founders == ["Solo Founder"]


def test_missing_confidence_is_derived(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)
    payload = {
        "description": "Just a description, no other fields.",
        "founders": [],
        "sector_keywords": [],
    }

    def fake_dispatch(self, *, url, schema):
        return payload

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    facts = client.scrape_facts("https://example.com").facts
    # Description only, no other populated fields: 0.5.
    assert facts.confidence == 0.5


def test_firecrawl_enrich_handles_missing_website(tmp_path) -> None:
    client = _make_client(tmp_path)
    facts = firecrawl_enrich(client, None)
    assert facts.confidence == 0.0
    assert client.stats.calls == 0

    facts = firecrawl_enrich(client, "")
    assert facts.confidence == 0.0
    facts = firecrawl_enrich(client, "   ")
    assert facts.confidence == 0.0
    assert client.stats.calls == 0


def test_firecrawl_enrich_passes_through_to_scrape(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)

    def fake_dispatch(self, *, url, schema):
        return dict(SAMPLE_PAYLOAD)

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    facts = firecrawl_enrich(client, "  https://example.com  ")
    assert facts.confidence == 1.0
    assert client.stats.calls == 1


def test_cache_round_trip_persists_to_disk(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)

    def fake_dispatch(self, *, url, schema):
        return dict(SAMPLE_PAYLOAD)

    monkeypatch.setattr(FirecrawlClient, "_dispatch", fake_dispatch)

    client.scrape_facts("https://example.com")
    cache_files = list(tmp_path.glob("*.json"))
    assert len(cache_files) == 1
    payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert payload["facts"]["description"] == SAMPLE_PAYLOAD["description"]
    assert payload["credits_used"] == DEFAULT_CREDITS_PER_CALL


def test_sanitise_helpers() -> None:
    assert _sanitise(None) is None
    assert _sanitise("foo — bar") == "foo - bar"
    assert _sanitise("foo – bar") == "foo - bar"
    assert _sanitise("plain") == "plain"
    # Empty string sanitises back to None.
    assert _sanitise("") is None


def test_post_process_strips_em_dashes_from_facts() -> None:
    facts = CompanyFacts(
        description="Lab — building agents.",
        last_funding_summary="Series A — led by Foo.",
        confidence=0.5,
    )
    cleaned = _post_process(facts)
    assert cleaned.description is not None
    assert "—" not in cleaned.description
    assert cleaned.last_funding_summary is not None
    assert "—" not in cleaned.last_funding_summary


def test_post_process_recomputes_confidence_from_populated_fields() -> None:
    """Model-emitted confidence is overridden so downstream `>0` checks behave."""
    # Model returned 0.0 but description + 3 other fields are populated.
    rich = CompanyFacts(
        description="A real description.",
        founders=["Alice"],
        sector_keywords=["agents"],
        last_funding_summary="Series B led by Foo.",
        confidence=0.0,
    )
    assert _post_process(rich).confidence == 1.0

    # Description only, nothing else → 0.5.
    description_only = CompanyFacts(description="Only this.", confidence=1.0)
    assert _post_process(description_only).confidence == 0.5

    # Empty payload → 0.0 regardless of model claim.
    empty = CompanyFacts(confidence=1.0)
    assert _post_process(empty).confidence == 0.0
