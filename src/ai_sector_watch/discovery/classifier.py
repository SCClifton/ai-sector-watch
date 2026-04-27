"""Sector + stage classification + summary, plus news-item kind classification."""

from __future__ import annotations

from ai_sector_watch.discovery.taxonomy import (
    SECTOR_TAGS,
    STAGES,
    is_valid_sector,
    is_valid_stage,
)
from ai_sector_watch.extraction.claude_client import ClaudeClient
from ai_sector_watch.extraction.prompts import (
    CLASSIFY_COMPANY_SYSTEM,
    CLASSIFY_COMPANY_USER_TEMPLATE,
    CLASSIFY_NEWS_SYSTEM,
    CLASSIFY_NEWS_USER_TEMPLATE,
)
from ai_sector_watch.extraction.schema import (
    CompanyClassification,
    NewsClassification,
)


def classify_company(
    client: ClaudeClient,
    *,
    name: str,
    context: str,
    max_tokens: int = 384,
) -> CompanyClassification:
    """Return sector tags, stage, and summary for `name`."""
    prompt = CLASSIFY_COMPANY_USER_TEMPLATE.format(
        name=name,
        context=context,
        sector_tags="\n".join(f"- {t}" for t in SECTOR_TAGS),
    )
    response = client.structured_call(
        system=CLASSIFY_COMPANY_SYSTEM,
        prompt=prompt,
        schema_cls=CompanyClassification,
        max_tokens=max_tokens,
    )
    return clean_classification(response.parsed)  # type: ignore[arg-type]


def classify_news(
    client: ClaudeClient,
    *,
    title: str,
    body: str,
    max_tokens: int = 128,
) -> NewsClassification:
    prompt = CLASSIFY_NEWS_USER_TEMPLATE.format(title=title, body=body)
    response = client.structured_call(
        system=CLASSIFY_NEWS_SYSTEM,
        prompt=prompt,
        schema_cls=NewsClassification,
        max_tokens=max_tokens,
    )
    return clean_news_classification(response.parsed)  # type: ignore[arg-type]


def clean_classification(c: CompanyClassification) -> CompanyClassification:
    """Drop any sector tag or stage value not in the canonical taxonomy."""
    safe_tags = [t for t in c.sector_tags if is_valid_sector(t)]
    if not safe_tags:
        # Fall back to a neutral generic tag rather than leaving the row empty.
        safe_tags = ["agents_and_orchestration"]
    safe_stage = c.stage if c.stage and is_valid_stage(c.stage) else None
    summary = (c.summary or "").replace("—", " ")
    return CompanyClassification(
        sector_tags=safe_tags,
        stage=safe_stage,
        summary=summary,
    )


def clean_news_classification(n: NewsClassification) -> NewsClassification:
    valid_kinds = {"funding", "launch", "hire", "partnership", "other"}
    kind = n.kind if n.kind in valid_kinds else "other"
    return NewsClassification(kind=kind, is_relevant=n.is_relevant)


def link_news_to_companies(
    *,
    mention_names: list[str],
    known_companies: list[tuple[str, str]],  # (name_normalised, company_id)
) -> list[str]:
    """Return the company IDs that match any extracted mention.

    Pure function. Match is exact on `normalised(name)`. The orchestrator
    upserts brand-new companies separately.
    """
    by_norm = dict(known_companies)
    out: list[str] = []
    seen: set[str] = set()
    for name in mention_names:
        norm = " ".join(name.lower().split())
        company_id = by_norm.get(norm)
        if company_id and company_id not in seen:
            out.append(company_id)
            seen.add(company_id)
    return out


__all__ = [
    "STAGES",
    "classify_company",
    "classify_news",
    "clean_classification",
    "clean_news_classification",
    "link_news_to_companies",
]
