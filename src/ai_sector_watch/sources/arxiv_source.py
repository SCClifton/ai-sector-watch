"""arXiv RSS sources for cs.AI / cs.LG / cs.RO categories.

Uses the standard arXiv RSS endpoints (the same shape as any RSS feed),
so we delegate to `RssSource`.
"""

from __future__ import annotations

from ai_sector_watch.sources.rss import RssSource


def arxiv_cs_ai() -> RssSource:
    return RssSource("arxiv_cs_ai", "https://export.arxiv.org/rss/cs.AI", kind="papers")


def arxiv_cs_lg() -> RssSource:
    return RssSource("arxiv_cs_lg", "https://export.arxiv.org/rss/cs.LG", kind="papers")


def arxiv_cs_cl() -> RssSource:
    return RssSource("arxiv_cs_cl", "https://export.arxiv.org/rss/cs.CL", kind="papers")


def arxiv_cs_cv() -> RssSource:
    return RssSource("arxiv_cs_cv", "https://export.arxiv.org/rss/cs.CV", kind="papers")


def arxiv_cs_ro() -> RssSource:
    return RssSource("arxiv_cs_ro", "https://export.arxiv.org/rss/cs.RO", kind="papers")
