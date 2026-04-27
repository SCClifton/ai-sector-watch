"""Tests for the RSS, sitemap, arXiv, and HuggingFace sources.

All tests are fixture-driven. No live network calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from ai_sector_watch.sources.arxiv_source import (
    arxiv_cs_ai,
    arxiv_cs_lg,
    arxiv_cs_ro,
)
from ai_sector_watch.sources.huggingface_papers import (
    HuggingFacePapers,
    parse_huggingface_payload,
)
from ai_sector_watch.sources.rss import RssSource, parse_feed_bytes
from ai_sector_watch.sources.sitemap import (
    capital_brief,
    parse_google_news_sitemap_bytes,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _patch_httpx_get(monkeypatch, *, body: bytes | None = None, status: int = 200) -> None:
    """Replace httpx.Client.get with a stub returning fixed bytes/status."""

    def fake_get(self, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("GET", url)
        return httpx.Response(status, request=request, content=body or b"")

    monkeypatch.setattr(httpx.Client, "get", fake_get)


def test_parse_feed_bytes_extracts_two_valid_entries() -> None:
    body = (FIXTURES / "sample_rss.xml").read_bytes()
    items = parse_feed_bytes(body, slug="sample")
    assert len(items) == 2
    assert items[0].title == "Australian AI startup Marqo raises seed"
    assert items[0].url == "https://example.com/post/1"
    assert items[0].source_slug == "sample"
    assert items[0].published_at is not None
    titles = {i.title for i in items}
    assert "" not in titles


def test_parse_feed_bytes_respects_limit() -> None:
    body = (FIXTURES / "sample_rss.xml").read_bytes()
    items = parse_feed_bytes(body, slug="sample", limit=1)
    assert len(items) == 1


def test_rss_source_fetches_via_http(monkeypatch) -> None:
    body = (FIXTURES / "sample_rss.xml").read_bytes()
    _patch_httpx_get(monkeypatch, body=body, status=200)
    source = RssSource("example", "https://example.com/feed.xml")
    items = source.fetch()
    assert len(items) == 2


def test_rss_source_raises_on_http_error(monkeypatch) -> None:
    _patch_httpx_get(monkeypatch, status=503)
    source = RssSource("bad", "https://example.com/bad")
    with pytest.raises(httpx.HTTPStatusError):
        source.fetch()


def test_parse_google_news_sitemap_bytes_extracts_items() -> None:
    body = (FIXTURES / "sample_capital_brief.xml").read_bytes()
    items = parse_google_news_sitemap_bytes(body, slug="capital_brief")
    assert len(items) >= 1
    assert items[0].title == "Australian quantum startups seize on Nvidia's Ising AI model"
    assert items[0].url.startswith("https://www.capitalbrief.com/article/")
    assert items[0].source_slug == "capital_brief"
    assert items[0].published_at is not None
    assert items[0].raw["publication"] == "Capital Brief"


def test_capital_brief_factory_uses_news_sitemap() -> None:
    source = capital_brief()
    assert source.slug == "capital_brief"
    assert source.kind == "news"
    assert source.url == "https://www.capitalbrief.com/sitemap/news.xml"


def test_arxiv_factories_have_distinct_slugs() -> None:
    sources = [arxiv_cs_ai(), arxiv_cs_lg(), arxiv_cs_ro()]
    slugs = {s.slug for s in sources}
    assert slugs == {"arxiv_cs_ai", "arxiv_cs_lg", "arxiv_cs_ro"}
    for s in sources:
        assert s.kind == "papers"
        assert s.url.startswith("https://export.arxiv.org/rss/")


def test_parse_huggingface_payload_skips_malformed() -> None:
    payload = json.loads((FIXTURES / "sample_huggingface.json").read_text())
    items = parse_huggingface_payload(payload)
    assert len(items) == 2
    assert items[0].title == "Sample paper title"
    assert items[0].url == "https://huggingface.co/papers/2604.01234"
    assert items[0].raw["upvotes"] == 12
    assert items[0].raw["authors"] == ["Jane Doe", "John Smith"]
    assert items[0].published_at is not None


def test_huggingface_source_fetches_via_http(monkeypatch) -> None:
    payload_bytes = (FIXTURES / "sample_huggingface.json").read_bytes()
    _patch_httpx_get(monkeypatch, body=payload_bytes, status=200)
    items = HuggingFacePapers().fetch()
    assert len(items) == 2


def test_source_base_requires_slug_and_kind() -> None:
    from ai_sector_watch.sources.base import SourceBase

    class NoSlug(SourceBase):
        kind = "news"

        def fetch(self, *, limit=None):
            return []

    with pytest.raises(ValueError):
        NoSlug()
