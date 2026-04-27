"""XML sitemap sources for publishers without RSS or Atom feeds."""

from __future__ import annotations

from datetime import UTC, datetime
from xml.etree import ElementTree

import httpx

from ai_sector_watch.sources.base import RawItem, SourceBase
from ai_sector_watch.sources.rss import DEFAULT_TIMEOUT, USER_AGENT

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
NEWS_NS = {
    **SITEMAP_NS,
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}


class GoogleNewsSitemapSource(SourceBase):
    """Fetch a Google News sitemap and emit one RawItem per URL entry."""

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
        """Fetch and parse the sitemap."""
        body = self._http_get()
        return parse_google_news_sitemap_bytes(body, slug=self.slug, limit=limit)


def parse_google_news_sitemap_bytes(
    body: bytes, *, slug: str, limit: int | None = None
) -> list[RawItem]:
    """Parse raw Google News sitemap bytes into RawItems."""
    root = ElementTree.fromstring(body)
    items: list[RawItem] = []
    for url_node in root.findall("sm:url", SITEMAP_NS):
        loc = _node_text(url_node, "sm:loc", SITEMAP_NS)
        news_node = url_node.find("news:news", NEWS_NS)
        title = _node_text(news_node, "news:title", NEWS_NS) if news_node is not None else None
        if not loc or not title:
            continue
        publication_date = (
            _node_text(news_node, "news:publication_date", NEWS_NS)
            if news_node is not None
            else None
        )
        publication_name = (
            _node_text(news_node, "news:publication/news:name", NEWS_NS)
            if news_node is not None
            else None
        )
        items.append(
            RawItem(
                source_slug=slug,
                url=loc,
                title=title,
                summary=None,
                published_at=_parse_datetime(publication_date),
                raw={"publication": publication_name},
            )
        )
        if limit is not None and len(items) >= limit:
            break
    return items


def capital_brief() -> GoogleNewsSitemapSource:
    """Return the Capital Brief Google News sitemap source."""
    return GoogleNewsSitemapSource(
        "capital_brief",
        "https://www.capitalbrief.com/sitemap/news.xml",
    )


def _node_text(
    node: ElementTree.Element | None, path: str, namespaces: dict[str, str]
) -> str | None:
    if node is None:
        return None
    child = node.find(path, namespaces)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
