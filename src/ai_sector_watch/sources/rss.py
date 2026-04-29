"""Generic RSS / Atom source built on `feedparser`."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import feedparser
import httpx

from ai_sector_watch.sources.base import RawItem, SourceBase

LOGGER = logging.getLogger(__name__)
USER_AGENT = "ai-sector-watch/0.1 (+aimap.cliftonfamily.co)"
DEFAULT_TIMEOUT = 30.0


class RssSource(SourceBase):
    """Fetch an RSS or Atom feed and emit one RawItem per entry."""

    kind = "news"

    def __init__(self, slug: str, url: str, *, kind: str = "news") -> None:
        super().__init__(slug=slug, kind=kind)
        self.url = url

    def _http_get(self) -> bytes:
        with httpx.Client(timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}) as c:
            response = c.get(self.url, follow_redirects=True)
            response.raise_for_status()
            return response.content

    def fetch(self, *, limit: int | None = None) -> list[RawItem]:
        body = self._http_get()
        return parse_feed_bytes(body, slug=self.slug, limit=limit)


def parse_feed_bytes(body: bytes, *, slug: str, limit: int | None = None) -> list[RawItem]:
    """Parse raw RSS/Atom bytes into `RawItem`s. Pure: no network."""
    parsed = feedparser.parse(body)
    items: list[RawItem] = []
    for entry in parsed.entries[: limit if limit else None]:
        published = _entry_datetime(entry)
        url = entry.get("link") or entry.get("id") or ""
        title = (entry.get("title") or "").strip()
        if not url or not title:
            LOGGER.debug("skipping malformed entry in %s: %s", slug, entry.get("id"))
            continue
        summary = entry.get("summary") or entry.get("description")
        items.append(
            RawItem(
                source_slug=slug,
                url=url,
                title=title,
                summary=summary,
                published_at=published,
                raw={
                    "id": entry.get("id"),
                    "tags": [t.get("term") for t in entry.get("tags", [])],
                    "author": entry.get("author"),
                },
            )
        )
    return items


def _entry_datetime(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(time.mktime(value), tz=UTC)
    return None


# Pre-baked RSS source factories from PRD section 7.


def techcrunch_ai() -> RssSource:
    return RssSource(
        "techcrunch_ai", "https://techcrunch.com/category/artificial-intelligence/feed/"
    )


def startup_daily_au() -> RssSource:
    return RssSource("startup_daily_au", "https://www.startupdaily.net/feed/")


def smartcompany_startups() -> RssSource:
    return RssSource(
        "smartcompany_startups",
        "https://www.smartcompany.com.au/startupsmart/feed/",
    )


def crunchbase_ai() -> RssSource:
    return RssSource("crunchbase_ai", "https://news.crunchbase.com/sections/ai/feed/")
