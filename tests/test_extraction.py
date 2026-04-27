"""Tests for the Claude extraction client.

All tests stub out `_dispatch()` so the live SDK is never invoked.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_sector_watch.extraction.claude_client import (
    BudgetExceeded,
    ClaudeClient,
    StructuredResponse,
    _rough_token_count,
)
from ai_sector_watch.extraction.schema import (
    CompanyClassification,
    CompanyMention,
    CompanyMentionList,
    NewsClassification,
)


def _make_client(tmp_path, *, budget_usd=2.0, model="claude-sonnet-4-6") -> ClaudeClient:
    return ClaudeClient(model=model, budget_usd=budget_usd, cache_dir=tmp_path)


def _stub_response(parsed, *, input_tokens=10, output_tokens=20) -> StructuredResponse:
    return StructuredResponse(
        parsed=parsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=0.0,  # populated by client
        cached=False,
    )


def test_structured_call_caches_result_on_second_invocation(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path)
    calls = {"count": 0}

    def fake_dispatch(self, *, system, prompt, schema_cls, max_tokens):
        calls["count"] += 1
        cost = self._estimate_cost(input_tokens=10, output_tokens=20)
        return StructuredResponse(
            parsed=schema_cls(mentions=[]),
            input_tokens=10,
            output_tokens=20,
            cost_usd=cost,
            cached=False,
        )

    monkeypatch.setattr(ClaudeClient, "_dispatch", fake_dispatch)

    a = client.structured_call(
        system="sys", prompt="p", schema_cls=CompanyMentionList, max_tokens=128
    )
    b = client.structured_call(
        system="sys", prompt="p", schema_cls=CompanyMentionList, max_tokens=128
    )
    assert calls["count"] == 1
    assert a.cached is False
    assert b.cached is True
    assert client.stats.cache_hits == 1


def test_budget_cap_blocks_further_calls(tmp_path, monkeypatch) -> None:
    client = _make_client(tmp_path, budget_usd=0.0001)

    def fake_dispatch(self, *, system, prompt, schema_cls, max_tokens):
        return StructuredResponse(
            parsed=schema_cls(mentions=[]),
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.0001,
            cached=False,
        )

    monkeypatch.setattr(ClaudeClient, "_dispatch", fake_dispatch)

    with pytest.raises(BudgetExceeded):
        client.structured_call(
            system="sys",
            prompt="p" * 4000,  # large prompt makes pre-flight estimate non-trivial
            schema_cls=CompanyMentionList,
            max_tokens=2000,
        )


def test_estimate_cost_uses_known_model_table() -> None:
    sonnet = ClaudeClient(model="claude-sonnet-4-6", budget_usd=10)._estimate_cost(
        input_tokens=1_000_000, output_tokens=0
    )
    opus = ClaudeClient(model="claude-opus-4-7", budget_usd=10)._estimate_cost(
        input_tokens=1_000_000, output_tokens=0
    )
    assert sonnet == pytest.approx(3.0, rel=1e-6)
    assert opus == pytest.approx(15.0, rel=1e-6)
    # Unknown model defaults to Sonnet pricing.
    unknown = ClaudeClient(model="claude-future-x", budget_usd=10)._estimate_cost(
        input_tokens=1_000_000, output_tokens=0
    )
    assert unknown == pytest.approx(3.0, rel=1e-6)


def test_rough_token_count_is_at_least_one() -> None:
    assert _rough_token_count("") == 1
    assert _rough_token_count("a") == 1
    assert _rough_token_count("a" * 8) == 2


def test_pydantic_schemas_round_trip_via_model_validate() -> None:
    mention = CompanyMention(
        name="Marqo", confidence=0.95, is_anz=True, city="Sydney", country="AU"
    )
    assert mention.is_anz is True
    classification = CompanyClassification(
        sector_tags=["foundation_models"],
        stage="seed",
        summary="Marqo is a vector search engine.",
    )
    assert classification.sector_tags == ["foundation_models"]
    news = NewsClassification(kind="funding", is_relevant=True)
    assert news.is_relevant is True


def test_company_classification_sector_tag_count_bounded() -> None:
    with pytest.raises(ValidationError):
        CompanyClassification(
            sector_tags=[],
            stage="seed",
            summary="Empty tag list should fail validation.",
        )
    with pytest.raises(ValidationError):
        CompanyClassification(
            sector_tags=["a", "b", "c", "d", "e"],
            stage="seed",
            summary="More than four tags should fail validation.",
        )
