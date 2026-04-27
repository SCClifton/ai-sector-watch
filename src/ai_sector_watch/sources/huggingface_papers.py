"""HuggingFace daily papers JSON API source."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from ai_sector_watch.sources.base import RawItem, SourceBase
from ai_sector_watch.sources.rss import DEFAULT_TIMEOUT, USER_AGENT

LOGGER = logging.getLogger(__name__)


class HuggingFacePapers(SourceBase):
    """Fetch the HuggingFace daily papers list (JSON API)."""

    slug = "huggingface_papers"
    kind = "papers"

    URL = "https://huggingface.co/api/daily_papers"

    def fetch(self, *, limit: int | None = None) -> list[RawItem]:
        with httpx.Client(timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}) as c:
            response = c.get(self.URL)
            response.raise_for_status()
            payload = response.json()
        return parse_huggingface_payload(payload, limit=limit)


def parse_huggingface_payload(payload: list[dict], *, limit: int | None = None) -> list[RawItem]:
    """Pure parser for the HF daily-papers JSON shape."""
    items: list[RawItem] = []
    for entry in payload[: limit if limit else None]:
        paper = entry.get("paper") or {}
        arxiv_id = paper.get("id") or entry.get("id")
        title = (paper.get("title") or entry.get("title") or "").strip()
        if not arxiv_id or not title:
            continue
        url = f"https://huggingface.co/papers/{arxiv_id}"
        summary = paper.get("summary") or entry.get("summary")
        published = _parse_date(entry.get("publishedAt"))
        items.append(
            RawItem(
                source_slug="huggingface_papers",
                url=url,
                title=title,
                summary=summary,
                published_at=published,
                raw={
                    "arxiv_id": arxiv_id,
                    "upvotes": entry.get("upvotes"),
                    "authors": [a.get("name") for a in paper.get("authors", [])],
                },
            )
        )
    return items


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
