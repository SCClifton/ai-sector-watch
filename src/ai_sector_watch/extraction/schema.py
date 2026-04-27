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
        ..., ge=0.0, le=1.0,
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


class CompanyClassification(BaseModel):
    """Sector tags and stage assigned by Claude."""

    sector_tags: list[str] = Field(
        ..., min_length=1, max_length=4,
        description="One to four sector tags from the canonical taxonomy.",
    )
    stage: str | None = Field(None, description="One of pre_seed, seed, series_a, series_b_plus, mature.")
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
