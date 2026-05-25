"""Tests for the Claude extraction client.

All tests stub out `_dispatch()` so the live SDK is never invoked.
"""

from __future__ import annotations

import pytest
from anthropic import RateLimitError
from pydantic import ValidationError

from ai_sector_watch.extraction import claude_client
from ai_sector_watch.extraction.claude_client import (
    ANTHROPIC_RPM_CAP,
    BudgetExceeded,
    ClaudeClient,
    StructuredResponse,
    _rough_token_count,
    _throttle_anthropic_call,
    _wait_anthropic_aware,
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


def test_throttle_spaces_calls_at_target_rpm(monkeypatch) -> None:
    """The module-wide throttle blocks until enough wall-clock has elapsed
    between successive `_dispatch` invocations."""
    sleeps: list[float] = []
    fake_clock = {"t": 1000.0}

    def fake_monotonic() -> float:
        return fake_clock["t"]

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        fake_clock["t"] += seconds

    monkeypatch.setattr(claude_client.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(claude_client.time, "sleep", fake_sleep)
    monkeypatch.setattr(claude_client, "_RATE_LIMITER_NEXT_AT", 0.0)

    # First call has no prior history -> no sleep.
    _throttle_anthropic_call()
    # Subsequent calls in a tight loop should each sleep ~ (60 / RPM).
    _throttle_anthropic_call()
    _throttle_anthropic_call()

    expected_interval = 60.0 / ANTHROPIC_RPM_CAP
    assert sleeps == [pytest.approx(expected_interval), pytest.approx(expected_interval)]


def test_wait_anthropic_aware_honours_retry_after_header() -> None:
    """A 429 with a `Retry-After` header should produce that wait verbatim
    (capped at 120 s), instead of the small exponential default."""

    class _FakeHeaders:
        def __init__(self, mapping: dict[str, str]) -> None:
            self._m = mapping

        def get(self, key: str, default=None):
            return self._m.get(key.lower(), default)

    class _FakeResponse:
        def __init__(self, headers: dict[str, str]) -> None:
            self.headers = _FakeHeaders({k.lower(): v for k, v in headers.items()})

    exc = RateLimitError.__new__(RateLimitError)
    exc.response = _FakeResponse({"retry-after": "45"})

    class _Outcome:
        def exception(self) -> BaseException:
            return exc

    class _State:
        outcome = _Outcome()
        attempt_number = 1
        seconds_since_start = 0.0
        idle_for = 0.0
        next_action = None

    assert _wait_anthropic_aware(_State()) == 45.0


def test_wait_anthropic_aware_falls_back_when_header_missing() -> None:
    """Without a `Retry-After` header the wait should be > 0 (exponential)."""
    exc = RateLimitError.__new__(RateLimitError)
    exc.response = None

    class _Outcome:
        def exception(self) -> BaseException:
            return exc

    class _State:
        outcome = _Outcome()
        attempt_number = 1
        seconds_since_start = 0.0
        idle_for = 0.0
        next_action = None

    assert _wait_anthropic_aware(_State()) > 0.0


# Avoid bleeding throttle state between this module's tests and the rest of
# the suite (the throttle keeps a `time.monotonic()` watermark in module
# state, and other tests may run on faster wall-clocks where the watermark
# would force unintended sleeps).
@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    claude_client._RATE_LIMITER_NEXT_AT = 0.0
    yield
    claude_client._RATE_LIMITER_NEXT_AT = 0.0
