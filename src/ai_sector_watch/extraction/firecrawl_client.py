"""Budget-capped, cached Firecrawl client.

Mirrors the `ClaudeClient` pattern in `claude_client.py`:

- Lazy auth (`FIRECRAWL_API_KEY`) so importing the module never hits the
  network or fails when the env var is unset (e.g. in CI).
- Per-run credit cap via `FIRECRAWL_BUDGET_CREDITS_PER_RUN` (default 200).
  A scrape with JSON-mode extract costs ~5 credits; the cap raises
  `FirecrawlBudgetExceeded` when the next call would push past the cap.
- Disk cache under `data/local/firecrawl_cache/{hash}.json`. The cache
  key is the URL plus the JSON-Schema hash so a schema change forces a
  re-scrape.
- Tests should monkey-patch `FirecrawlClient._dispatch()` to avoid
  hitting the live SDK.

The public entry point for the pipeline is `firecrawl_enrich(client, website)`
which returns a `CompanyFacts`. It tolerates missing websites and scrape
failures by returning a low-confidence empty `CompanyFacts`, so the
caller never has to special-case None.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ai_sector_watch.config import REPO_ROOT
from ai_sector_watch.extraction.schema import CompanyFacts

LOGGER = logging.getLogger(__name__)
CACHE_DIR = REPO_ROOT / "data" / "local" / "firecrawl_cache"

# A scrape (1 credit) plus JSON-mode extract (4 credits) = 5 credits per call.
DEFAULT_CREDITS_PER_CALL = 5
DEFAULT_BUDGET_CREDITS_PER_RUN = 200

ENRICH_PROMPT = (
    "Extract authoritative facts about this company from its own website. "
    "Use only what the page explicitly states. Leave fields null when the "
    "page does not say. Do not use em dashes in the description; prefer a "
    "colon, comma, or ' - '."
)

_EM_DASH_PATTERN = re.compile(r"\s*[—–]\s*")


class FirecrawlBudgetExceeded(RuntimeError):
    """Raised when a scrape would push the run total past the credit cap."""


@dataclass
class FirecrawlStats:
    """Running totals for a single FirecrawlClient instance."""

    calls: int = 0
    cache_hits: int = 0
    credits_used: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FirecrawlResult:
    """A typed CompanyFacts plus the credits it consumed."""

    facts: CompanyFacts
    credits_used: int
    cached: bool


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _sanitise(text: str | None) -> str | None:
    """Replace em dash and en dash with a hyphen for user-facing copy."""
    if text is None:
        return None
    return _EM_DASH_PATTERN.sub(" - ", text).strip() or None


class FirecrawlClient:
    """Thin wrapper around the Firecrawl Python SDK with budget + caching."""

    def __init__(
        self,
        *,
        budget_credits: int | None = None,
        credits_per_call: int = DEFAULT_CREDITS_PER_CALL,
        cache_dir: Path | None = None,
    ) -> None:
        self.budget_credits = (
            budget_credits
            if budget_credits is not None
            else int(
                os.environ.get(
                    "FIRECRAWL_BUDGET_CREDITS_PER_RUN",
                    str(DEFAULT_BUDGET_CREDITS_PER_RUN),
                )
            )
        )
        self.credits_per_call = credits_per_call
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = FirecrawlStats()
        self._client = None  # lazy

    @property
    def firecrawl(self):
        """Lazy import + lazy auth so tests can avoid the dependency."""
        if self._client is None:
            from firecrawl import Firecrawl

            api_key = os.environ.get("FIRECRAWL_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "FIRECRAWL_API_KEY not set; run via op run --account my.1password.com "
                    "--env-file=.env.local -- ..."
                )
            self._client = Firecrawl(api_key=api_key)
        return self._client

    # -- public ----------------------------------------------------------

    def scrape_facts(self, url: str) -> FirecrawlResult:
        """Scrape `url` and return JSON-mode-extracted CompanyFacts.

        Raises FirecrawlBudgetExceeded when the next call would exceed
        the per-run credit cap. On SDK failure, records the failure on
        `stats.failures` and returns a low-confidence empty CompanyFacts
        result so the caller can keep going.
        """
        schema = CompanyFacts.model_json_schema()
        cache_key = _hash(url, json.dumps(schema, sort_keys=True))

        cached = self._read_cache(cache_key)
        if cached is not None:
            try:
                facts = CompanyFacts.model_validate(cached["facts"])
            except ValidationError as exc:
                LOGGER.warning("firecrawl cache for %s failed validation: %s", cache_key[:8], exc)
            else:
                self.stats.cache_hits += 1
                return FirecrawlResult(
                    facts=facts,
                    credits_used=int(cached.get("credits_used", 0)),
                    cached=True,
                )

        if self.stats.credits_used + self.credits_per_call > self.budget_credits:
            raise FirecrawlBudgetExceeded(
                f"would exceed {self.budget_credits}-credit cap "
                f"(used {self.stats.credits_used}, next call costs {self.credits_per_call})"
            )

        try:
            facts_json = self._dispatch(url=url, schema=schema)
        except Exception as exc:  # noqa: BLE001 - any SDK failure is a soft failure here
            self.stats.calls += 1
            self.stats.failures.append(f"{url}: {type(exc).__name__}: {exc}")
            LOGGER.warning("firecrawl scrape failed for %s: %s", url, exc)
            return FirecrawlResult(facts=CompanyFacts.empty(), credits_used=0, cached=False)

        try:
            facts = self._coerce_facts(facts_json)
        except ValidationError as exc:
            self.stats.calls += 1
            self.stats.failures.append(f"{url}: schema validation: {exc}")
            LOGGER.warning("firecrawl response for %s did not validate: %s", url, exc)
            return FirecrawlResult(facts=CompanyFacts.empty(), credits_used=0, cached=False)

        facts = _post_process(facts)

        self.stats.calls += 1
        self.stats.credits_used += self.credits_per_call

        self._write_cache(
            cache_key,
            facts=facts.model_dump(mode="json"),
            credits_used=self.credits_per_call,
        )
        return FirecrawlResult(facts=facts, credits_used=self.credits_per_call, cached=False)

    # -- live dispatch (override-friendly for tests) ---------------------

    def _dispatch(self, *, url: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Make the actual SDK call. Returns the raw json dict the SDK gave back."""
        from firecrawl.v2.types import JsonFormat

        formats = [
            "markdown",
            JsonFormat(type="json", prompt=ENRICH_PROMPT, schema=schema),
        ]
        document = self.firecrawl.scrape(url, formats=formats, only_main_content=True)
        if document is None or not getattr(document, "json", None):
            raise RuntimeError("firecrawl returned no json payload")
        return document.json  # type: ignore[no-any-return]

    # -- internals --------------------------------------------------------

    def _coerce_facts(self, raw: dict[str, Any]) -> CompanyFacts:
        """Best-effort coercion of the SDK json payload into CompanyFacts.

        The model can return numeric strings or omit list fields entirely;
        normalise here before letting Pydantic validate.
        """
        cleaned: dict[str, Any] = dict(raw)

        founded = cleaned.get("founded_year")
        if isinstance(founded, str):
            try:
                cleaned["founded_year"] = int(founded.strip())
            except ValueError:
                cleaned["founded_year"] = None

        for list_field in ("founders", "sector_keywords"):
            value = cleaned.get(list_field)
            if value is None:
                cleaned[list_field] = []
            elif isinstance(value, str):
                cleaned[list_field] = [value]

        confidence = cleaned.get("confidence")
        if confidence is None:
            cleaned["confidence"] = _derive_confidence(cleaned)
        elif isinstance(confidence, str):
            try:
                cleaned["confidence"] = float(confidence)
            except ValueError:
                cleaned["confidence"] = _derive_confidence(cleaned)

        return CompanyFacts.model_validate(cleaned)

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> dict | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            LOGGER.warning("firecrawl cache read failed for %s: %s", key[:8], exc)
            return None

    def _write_cache(self, key: str, *, facts: dict, credits_used: int) -> None:
        path = self._cache_path(key)
        try:
            path.write_text(
                json.dumps({"facts": facts, "credits_used": credits_used}, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            LOGGER.warning("firecrawl cache write failed for %s: %s", key[:8], exc)


def _derive_confidence(raw: dict[str, Any]) -> float:
    """Fallback confidence: 1 if description plus another field present, else 0.5/0.0."""
    has_description = bool(raw.get("description"))
    populated = sum(
        1
        for k in (
            "founded_year",
            "founders",
            "city",
            "country",
            "sector_keywords",
            "last_funding_summary",
        )
        if raw.get(k)
    )
    if has_description and populated >= 1:
        return 1.0
    if has_description or populated >= 1:
        return 0.5
    return 0.0


def _post_process(facts: CompanyFacts) -> CompanyFacts:
    """Sanitise user-facing strings and recompute confidence from populated fields.

    The LLM tends to either echo the schema default (0.0) or hallucinate a
    high value regardless of how much it actually filled in. Compute it
    deterministically here so downstream `confidence > 0` checks behave.
    """
    cleaned_description = _sanitise(facts.description)
    cleaned_summary = _sanitise(facts.last_funding_summary)
    populated_other = sum(
        1
        for v in (
            facts.founded_year,
            facts.city,
            facts.country,
            cleaned_summary,
        )
        if v
    )
    if facts.founders:
        populated_other += 1
    if facts.sector_keywords:
        populated_other += 1
    if cleaned_description and populated_other >= 1:
        confidence = 1.0
    elif cleaned_description or populated_other >= 1:
        confidence = 0.5
    else:
        confidence = 0.0
    return facts.model_copy(
        update={
            "description": cleaned_description,
            "last_funding_summary": cleaned_summary,
            "confidence": confidence,
        }
    )


def firecrawl_enrich(client: FirecrawlClient, website: str | None) -> CompanyFacts:
    """Pipeline-facing helper: enrich one company website into CompanyFacts.

    Returns CompanyFacts.empty() (confidence=0) when:
    - website is None or blank,
    - the SDK call raised any exception,
    - the response did not validate against CompanyFacts.

    Raises FirecrawlBudgetExceeded when the next call would push past
    the credit cap; the caller (orchestrator) catches this and records
    a partial run, same shape as BudgetExceeded in claude_client.
    """
    if not website or not website.strip():
        return CompanyFacts.empty()
    result = client.scrape_facts(website.strip())
    return result.facts
