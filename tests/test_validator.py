"""Tests for discovery.validator and discovery.classifier."""

from __future__ import annotations

from ai_sector_watch.discovery.classifier import (
    classify_company,
    classify_news,
    clean_classification,
    clean_news_classification,
    link_news_to_companies,
)
from ai_sector_watch.discovery.validator import is_acceptable, validate_company
from ai_sector_watch.extraction.claude_client import (
    ClaudeClient,
    StructuredResponse,
)
from ai_sector_watch.extraction.schema import (
    CompanyClassification,
    CompanyValidation,
    NewsClassification,
)


def _stub_client(tmp_path, *, responses: dict) -> ClaudeClient:
    """Build a ClaudeClient whose `_dispatch` returns canned objects by schema name."""
    client = ClaudeClient(model="claude-sonnet-4-6", budget_usd=2.0, cache_dir=tmp_path)

    def fake_dispatch(self, *, system, prompt, schema_cls, max_tokens):
        parsed = responses[schema_cls.__name__]
        cost = self._estimate_cost(input_tokens=10, output_tokens=20)
        return StructuredResponse(
            parsed=parsed,
            input_tokens=10,
            output_tokens=20,
            cost_usd=cost,
            cached=False,
        )

    client._dispatch = fake_dispatch.__get__(client, ClaudeClient)
    return client


# ----- validator -----------------------------------------------------------


def test_validate_company_returns_pydantic_object(tmp_path) -> None:
    client = _stub_client(
        tmp_path,
        responses={
            "CompanyValidation": CompanyValidation(
                is_valid=True,
                is_ai_company=True,
                reasoning="It's Marqo, a real Sydney vector search company.",
                canonical_name=None,
            ),
        },
    )
    result = validate_company(client, name="Marqo", context="Sydney vector search startup")
    assert result.is_valid is True
    assert result.is_ai_company is True
    assert is_acceptable(result) is True


def test_is_acceptable_rejects_non_ai_companies() -> None:
    not_ai = CompanyValidation(
        is_valid=True, is_ai_company=False, reasoning="It's a fashion brand."
    )
    assert is_acceptable(not_ai) is False


# ----- classifier ----------------------------------------------------------


def test_classify_company_returns_cleaned_classification(tmp_path) -> None:
    client = _stub_client(
        tmp_path,
        responses={
            "CompanyClassification": CompanyClassification(
                sector_tags=["foundation_models", "not_real_tag"],
                stage="not_real_stage",
                summary="Some summary — with em dash.",
            ),
        },
    )
    result = classify_company(client, name="X", context="ctx")
    assert "foundation_models" in result.sector_tags
    assert "not_real_tag" not in result.sector_tags
    assert result.stage is None  # invalid stage stripped
    assert "—" not in result.summary  # em dash removed


def test_clean_classification_falls_back_when_all_tags_invalid() -> None:
    in_ = CompanyClassification(
        sector_tags=["bogus", "also_bogus"],
        stage="seed",
        summary="ok",
    )
    out = clean_classification(in_)
    assert out.sector_tags == ["agents_and_orchestration"]
    assert out.stage == "seed"


def test_classify_news_pins_to_known_kinds(tmp_path) -> None:
    client = _stub_client(
        tmp_path,
        responses={
            "NewsClassification": NewsClassification(kind="weird_kind", is_relevant=True),
        },
    )
    result = classify_news(client, title="t", body="b")
    assert result.kind == "other"
    assert result.is_relevant is True


def test_clean_news_classification_passes_known_kinds() -> None:
    in_ = NewsClassification(kind="funding", is_relevant=True)
    out = clean_news_classification(in_)
    assert out.kind == "funding"


# ----- link_news_to_companies ---------------------------------------------


def test_link_news_to_companies_matches_normalised_names() -> None:
    known = [("marqo", "uuid-marqo"), ("relevance ai", "uuid-relevance")]
    ids = link_news_to_companies(
        mention_names=["Marqo", "Relevance AI", "  marqo  "],
        known_companies=known,
    )
    # De-duped, in the order first seen.
    assert ids == ["uuid-marqo", "uuid-relevance"]


def test_link_news_to_companies_skips_unknown_names() -> None:
    known = [("marqo", "uuid-marqo")]
    ids = link_news_to_companies(
        mention_names=["Unknown Co", "Marqo"],
        known_companies=known,
    )
    assert ids == ["uuid-marqo"]
