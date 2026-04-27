"""Pydantic schemas for Claude-extracted entities.

These schemas double as JSON-Schema sources passed to the Anthropic SDK so
the model is forced into a structured response, and as the typed shape used
by the rest of the pipeline.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CompanyMention(BaseModel):
    """One company name extracted from a single source item."""

    name: str = Field(..., description="Exact company name as it appears.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence that this is a real AI-native or AI-applied company.",
    )
    is_anz: bool = Field(
        ..., description="True if the company is headquartered in Australia or New Zealand."
    )
    city: str | None = Field(None, description="City if mentioned or known.")
    country: str | None = Field(None, description="Country code: AU, NZ, or other.")


class CompanyMentionList(BaseModel):
    """Top-level container the Claude `extract_companies` prompt returns."""

    mentions: list[CompanyMention] = Field(default_factory=list)


class CompanyValidation(BaseModel):
    """Output of the validate prompt (per-candidate sanity check)."""

    is_valid: bool
    is_ai_company: bool
    reasoning: str
    canonical_name: str | None = None
    website: str | None = Field(
        None,
        description=(
            "Company website URL if the article mentions it or you know it "
            "with high confidence (e.g. linked in the article). Null if unknown."
        ),
    )


class CompanyClassification(BaseModel):
    """Sector tags and stage assigned by Claude."""

    sector_tags: list[str] = Field(
        ...,
        min_length=1,
        max_length=4,
        description="One to four sector tags from the canonical taxonomy.",
    )
    stage: str | None = Field(
        None, description="One of pre_seed, seed, series_a, series_b_plus, mature."
    )
    summary: str = Field(..., description="One-paragraph summary, no em dashes.")


class FundingExtraction(BaseModel):
    """Optional funding-event detail when a news item describes a round."""

    has_funding_event: bool
    announced_on: date | None = None
    stage: str | None = None
    amount_usd: float | None = None
    currency_raw: str | None = None
    lead_investor: str | None = None
    investors: list[str] = Field(default_factory=list)


class NewsClassification(BaseModel):
    """Kind tag for a news item."""

    kind: str = Field(..., description="funding | launch | hire | partnership | other")
    is_relevant: bool = Field(
        ...,
        description="True if the item is relevant to the ANZ AI ecosystem.",
    )


class CompanyFacts(BaseModel):
    """Firecrawl-extracted facts about a company from its own website.

    Used as additional context for the classifier and for direct upsert
    of structured fields (founded_year, founders, etc) on the company
    row. `confidence` is 0 when the scrape returned nothing usable and
    rises as more fields come back populated.
    """

    founded_year: int | None = Field(
        None,
        description="Year the company was founded, if stated on the website.",
        ge=1900,
        le=2100,
    )
    description: str | None = Field(
        None,
        description=(
            "One or two sentence company description in the company's own "
            "words. Do not use em dashes; use a colon, comma, or ' - ' instead."
        ),
    )
    founders: list[str] = Field(
        default_factory=list,
        description="Founder names if listed on About / Team / LinkedIn-style pages.",
    )
    city: str | None = Field(None, description="HQ city if stated.")
    country: str | None = Field(None, description="HQ country code (AU, NZ, US, ...) if stated.")
    sector_keywords: list[str] = Field(
        default_factory=list,
        description=(
            "Free-form sector / category keywords pulled from the page "
            "(vector search, RAG, biotech, ...)."
        ),
    )
    last_funding_summary: str | None = Field(
        None,
        description=(
            "Most recent funding event in one short sentence, if mentioned "
            "(round, lead, amount)."
        ),
    )
    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="0 when scrape failed or empty; rises as more fields come back populated.",
    )

    @classmethod
    def empty(cls) -> CompanyFacts:
        """Low-confidence empty placeholder used when no website is known or scrape failed."""
        return cls(confidence=0.0)
