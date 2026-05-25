"""Budget-capped, cached Claude client.

All extraction prompts go through `ClaudeClient.structured_call()` which:

- Enforces a per-run USD spend cap (`ANTHROPIC_BUDGET_USD_PER_RUN`).
- Caches successful responses on disk by `(prompt_hash, schema_hash, model)`.
- Returns Pydantic-validated structured output via the SDK's `tool_use` shape.

The cap is conservative: we estimate cost from `usage.input_tokens` /
`usage.output_tokens` returned by the SDK using a simple per-1M rate table.
When the running total crosses the cap, every subsequent call raises
`BudgetExceeded` and the orchestrator records the partial run.

Tests should monkey-patch `ClaudeClient._dispatch()` to avoid live API calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from anthropic import APIConnectionError, RateLimitError
from pydantic import BaseModel, ValidationError
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_combine,
    wait_exponential,
    wait_random,
)

from ai_sector_watch.config import REPO_ROOT, get_config

LOGGER = logging.getLogger(__name__)
CACHE_DIR = REPO_ROOT / "data" / "local" / "claude_cache"

# --- Process-wide rate limiter ------------------------------------------------
#
# Anthropic's tier-1 RPM ceiling for Haiku is ~50; we throttle to a conservative
# 30 RPM (one call every 2 s) so even when several `_extract_*` helpers fire
# back-to-back from the weekly pipeline, we never burst above the limit. The
# bucket is a module-level singleton so all `ClaudeClient` instances share it.
ANTHROPIC_RPM_CAP = 30
_RATE_LIMITER_LOCK = threading.Lock()
_RATE_LIMITER_NEXT_AT = 0.0


def _throttle_anthropic_call() -> None:
    """Block until at least 60/ANTHROPIC_RPM_CAP seconds have passed since the
    previous call. Safe across threads via a module-level lock."""
    global _RATE_LIMITER_NEXT_AT
    interval = 60.0 / ANTHROPIC_RPM_CAP
    with _RATE_LIMITER_LOCK:
        now = time.monotonic()
        wait = _RATE_LIMITER_NEXT_AT - now
        if wait > 0:
            time.sleep(wait)
            now += wait
        _RATE_LIMITER_NEXT_AT = now + interval


# --- Retry-After-aware wait for tenacity --------------------------------------
_FALLBACK_WAIT = wait_combine(
    wait_exponential(multiplier=2, min=2, max=120),
    wait_random(0, 1),
)


def _wait_anthropic_aware(retry_state: RetryCallState) -> float:
    """Tenacity `wait` callable that honours Anthropic's `Retry-After` header on
    429 responses. Falls back to exponential backoff (+ jitter) for any other
    error or when the header is absent. Each retry attempt of a `_dispatch`
    call counts against the org's rate-limit counter, so waiting at least the
    server-suggested duration is what stops the "20 rate limit hits in 24h"
    notification emails from re-firing each week.
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, RateLimitError):
        retry_after = None
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None) if response is not None else None
        if headers is not None:
            raw = headers.get("retry-after") or headers.get("Retry-After")
            if raw is not None:
                try:
                    retry_after = float(raw)
                except (TypeError, ValueError):
                    retry_after = None
        if retry_after is not None and retry_after > 0:
            # Cap at 120 s so a misconfigured upstream can't stall the run for
            # the whole 30-minute workflow timeout.
            return min(retry_after, 120.0)
    return _FALLBACK_WAIT(retry_state)

# Per-1M-token rates in USD. Conservative numbers; intentionally on the
# high side so the budget cap is hit early rather than late.
PRICING_PER_1M_USD: dict[str, tuple[float, float]] = {
    # model -> (input_per_1m, output_per_1m)
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
}

T = TypeVar("T", bound=BaseModel)


class BudgetExceeded(RuntimeError):
    """Raised when a prompt would push the run total above the cap."""


@dataclass
class CallStats:
    """Running totals for a single ClaudeClient instance."""

    calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StructuredResponse:
    """A typed-out Pydantic instance plus the raw token counts that produced it."""

    parsed: BaseModel
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cached: bool


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class ClaudeClient:
    """Thin wrapper around the Anthropic SDK with budget + caching."""

    def __init__(
        self,
        *,
        model: str | None = None,
        budget_usd: float | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        cfg = get_config()
        self.model = model or cfg.anthropic_model
        self.budget_usd = budget_usd if budget_usd is not None else cfg.anthropic_budget_usd_per_run
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = CallStats()
        self._client = None  # lazy

    @property
    def anthropic(self):
        """Lazy import + lazy auth so tests can avoid the dependency."""
        if self._client is None:
            from anthropic import Anthropic

            cfg = get_config()
            if not cfg.anthropic_api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set; run via op run --env-file=.env.local -- ..."
                )
            self._client = Anthropic(api_key=cfg.anthropic_api_key)
        return self._client

    # -- public ----------------------------------------------------------

    def structured_call(
        self,
        *,
        system: str,
        prompt: str,
        schema_cls: type[T],
        max_tokens: int = 1024,
    ) -> StructuredResponse:
        """Run a single Claude call with a Pydantic-validated response.

        Caches on `(model, system, prompt, schema_cls.__name__)`.
        """
        cache_key = _hash(self.model, system, prompt, schema_cls.__name__)
        cached = self._read_cache(cache_key)
        if cached is not None:
            try:
                parsed = schema_cls.model_validate(cached["parsed"])
            except ValidationError as exc:
                LOGGER.warning("cache for %s failed validation: %s", cache_key[:8], exc)
            else:
                self.stats.cache_hits += 1
                return StructuredResponse(
                    parsed=parsed,
                    input_tokens=cached["input_tokens"],
                    output_tokens=cached["output_tokens"],
                    cost_usd=cached["cost_usd"],
                    cached=True,
                )

        # Budget pre-flight. Use a rough estimate of the prompt's input tokens
        # plus the maximum output tokens to decide whether to dispatch.
        estimated_cost = self._estimate_cost(
            input_tokens=_rough_token_count(system) + _rough_token_count(prompt),
            output_tokens=max_tokens,
        )
        if self.stats.cost_usd + estimated_cost > self.budget_usd:
            raise BudgetExceeded(
                f"would exceed ${self.budget_usd:.2f} cap "
                f"(spent ${self.stats.cost_usd:.4f}, estimated ${estimated_cost:.4f})"
            )

        result = self._dispatch(
            system=system,
            prompt=prompt,
            schema_cls=schema_cls,
            max_tokens=max_tokens,
        )

        self.stats.calls += 1
        self.stats.input_tokens += result.input_tokens
        self.stats.output_tokens += result.output_tokens
        self.stats.cost_usd += result.cost_usd
        self._write_cache(
            cache_key,
            parsed=result.parsed.model_dump(mode="json"),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
        )
        return result

    # -- live dispatch (override-friendly for tests) ---------------------

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        stop=stop_after_attempt(6),
        wait=_wait_anthropic_aware,
        reraise=True,
    )
    def _dispatch(
        self,
        *,
        system: str,
        prompt: str,
        schema_cls: type[T],
        max_tokens: int,
    ) -> StructuredResponse:
        """Make the actual API call. Returns a StructuredResponse.

        Retries on RateLimitError (429) and APIConnectionError up to 6 attempts.
        The wait between retries honours the server's `Retry-After` header on
        429s (so we don't immediately re-hit the same rate window), falling
        back to exponential backoff + jitter otherwise. Each call also passes
        through `_throttle_anthropic_call()`, a module-wide token bucket
        capping us at `ANTHROPIC_RPM_CAP` requests/minute. Tests that replace
        `_dispatch` on the instance or class bypass the retry decorator and
        the throttle entirely.
        """
        _throttle_anthropic_call()
        tool = {
            "name": "emit_" + schema_cls.__name__.lower(),
            "description": f"Return a {schema_cls.__name__} object.",
            "input_schema": schema_cls.model_json_schema(),
        }
        response = self.anthropic.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": prompt}],
        )
        block = next(b for b in response.content if b.type == "tool_use")
        parsed = schema_cls.model_validate(block.input)
        usage = response.usage
        cost = self._estimate_cost(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return StructuredResponse(
            parsed=parsed,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            cached=False,
        )

    # -- internals --------------------------------------------------------

    def _estimate_cost(self, *, input_tokens: int, output_tokens: int) -> float:
        try:
            in_rate, out_rate = PRICING_PER_1M_USD[self.model]
        except KeyError:
            # Unknown model: assume Sonnet-tier pricing.
            in_rate, out_rate = PRICING_PER_1M_USD["claude-sonnet-4-6"]
        return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> dict | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            LOGGER.warning("cache read failed for %s: %s", key[:8], exc)
            return None

    def _write_cache(
        self,
        key: str,
        *,
        parsed: dict,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        path = self._cache_path(key)
        try:
            path.write_text(
                json.dumps(
                    {
                        "parsed": parsed,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": cost_usd,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            LOGGER.warning("cache write failed for %s: %s", key[:8], exc)


def _rough_token_count(text: str) -> int:
    """Cheap, approximate: 1 token per 4 characters. Good enough for budgeting."""
    return max(1, len(text) // 4)
