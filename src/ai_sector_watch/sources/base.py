"""Abstract base class for ingestion sources.

Every source returns a list of `RawItem`s — minimal, source-agnostic
news/paper records that the extractor can work on. Sources never write
to Supabase; that's the orchestrator's job.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RawItem:
    """Minimal source-agnostic item shape produced by every fetcher."""

    source_slug: str
    url: str
    title: str
    summary: str | None
    published_at: datetime | None
    raw: dict[str, Any] = field(default_factory=dict)


class SourceBase(ABC):
    """Subclass and implement `fetch()` to add a new source.

    Subclasses must set `slug` (matches `docs/sources.md`) and `kind`
    (one of `news`, `papers`, `blog`, `launches`, `api`).
    """

    slug: str
    kind: str

    def __init__(self, *, slug: str | None = None, kind: str | None = None) -> None:
        if slug:
            self.slug = slug
        if kind:
            self.kind = kind
        if not getattr(self, "slug", None):
            raise ValueError(f"{type(self).__name__} must set `slug`")
        if not getattr(self, "kind", None):
            raise ValueError(f"{type(self).__name__} must set `kind`")

    @abstractmethod
    def fetch(self, *, limit: int | None = None) -> list[RawItem]:
        """Return the latest items from this source.

        Implementations should:
        - Be idempotent (no internal state between calls).
        - Tolerate network errors by raising so the orchestrator can log
          and skip; partial returns are fine.
        - Honour the optional `limit` if cheap to do so.
        """

    def __repr__(self) -> str:  # pragma: no cover — trivial
        return f"<{type(self).__name__} slug={self.slug!r}>"
