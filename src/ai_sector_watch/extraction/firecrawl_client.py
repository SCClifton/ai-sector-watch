"""Budget-capped, cached Firecrawl enrichment client.

The pipeline-facing path pulls markdown from the company homepage, selected
company pages, and recent search results, then asks our Claude client to emit
the existing `CompanyFacts` schema. Firecrawl JSON mode is intentionally kept
out of the pipeline path to avoid paying extract credits on every page.

The older `scrape_facts()` method remains for compatibility with existing
tests and callers, but new enrichment should use `firecrawl_enrich()`.
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
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, ValidationError

from ai_sector_watch.config import REPO_ROOT
from ai_sector_watch.extraction.claude_client import BudgetExceeded, ClaudeClient
from ai_sector_watch.extraction.schema import CompanyFacts

LOGGER = logging.getLogger(__name__)
CACHE_DIR = REPO_ROOT / "data" / "local" / "firecrawl_cache"

# Legacy JSON-mode scrape: 1 scrape credit + 4 JSON extract credits.
DEFAULT_CREDITS_PER_CALL = 5
DEFAULT_CREDITS_PER_ENRICH = 8
DEFAULT_BUDGET_CREDITS_PER_RUN = 200

COMPANY_PAGE_KEYWORDS = (
    "about",
    "team",
    "leadership",
    "people",
    "founders",
    "company",
)
MAX_COMPANY_PAGES = 3
MAX_EXTRA_COMPANY_PAGES_FOR_ENRICH = 2
MAX_NEWS_RESULTS_FOR_ENRICH = 2
SEARCH_RESULTS_LIMIT = 10
SEARCH_TBS_LAST_YEAR = "qdr:y"
MAX_MARKDOWN_CHARS_PER_SOURCE = 6_000

BLOCKED_NEWS_DOMAINS = {
    "linkedin.com",
    "x.com",
    "twitter.com",
    "threads.net",
    "bsky.app",
    "reddit.com",
}

ENRICH_PROMPT = (
    "Extract authoritative facts about this company from the supplied source excerpts. "
    "Use only what the excerpts explicitly state. Leave fields null or empty when the "
    "sources do not say. Do not use em dashes in the description; prefer a colon, comma, "
    "or ' - '. Include evidence_urls containing only URLs from the supplied excerpts that "
    "support the extracted facts."
)

_EM_DASH_PATTERN = re.compile(r"\s*[—–]\s*")


class FirecrawlBudgetExceeded(RuntimeError):
    """Raised when a Firecrawl operation would push the run past the credit cap."""


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


@dataclass(frozen=True)
class MarkdownDocument:
    """Markdown scraped from one source URL."""

    url: str
    markdown: str
    title: str | None = None


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


def _normalise_url(url: str) -> str:
    """Return a stable absolute URL string for dedupe and cache keys."""
    candidate = url.strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = "https://" + candidate
    parsed = urlparse(candidate)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or ""
    return urlunparse((parsed.scheme.lower() or "https", netloc, path, "", "", ""))


def _domain(url: str) -> str:
    netloc = urlparse(_normalise_url(url)).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _same_domain(left: str, right: str) -> bool:
    return _domain(left) == _domain(right)


def _is_blocked_news_url(url: str) -> bool:
    domain = _domain(url)
    return any(
        domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_NEWS_DOMAINS
    )


def _candidate_page_matches(url: str, title: str | None) -> bool:
    haystack = " ".join([url, title or ""]).lower()
    return any(keyword in haystack for keyword in COMPANY_PAGE_KEYWORDS)


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
        self._client = None

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

    def find_company_pages(self, website: str) -> list[str]:
        """Use Firecrawl /map to find relevant company-domain pages."""
        root_url = _normalise_url(website)
        self._ensure_budget(1)
        try:
            pages = self._find_company_pages_unmetered(root_url)
        except Exception as exc:  # noqa: BLE001
            self.stats.calls += 1
            self.stats.failures.append(f"{root_url}: map: {type(exc).__name__}: {exc}")
            LOGGER.warning("firecrawl map failed for %s: %s", root_url, exc)
            return []
        self._record_firecrawl_spend(credits=1)
        return pages

    def fetch_company_news(self, name: str, limit: int = 3) -> list[dict[str, str]]:
        """Search recent web results for company leadership/funding coverage and scrape them."""
        self._ensure_budget(2 + limit)
        try:
            docs = self._fetch_company_news_unmetered(name=name, limit=limit)
        except Exception as exc:  # noqa: BLE001
            self.stats.calls += 1
            self.stats.failures.append(f"{name}: search: {type(exc).__name__}: {exc}")
            LOGGER.warning("firecrawl search failed for %s: %s", name, exc)
            return []
        self._record_firecrawl_spend(credits=2 + len(docs))
        return [doc.__dict__ for doc in docs]

    def scrape_facts(self, url: str) -> FirecrawlResult:
        """Scrape `url` and return JSON-mode-extracted CompanyFacts.

        This is the legacy path from issue #33. It is not used by the weekly
        pipeline after issue #39, but keeping it avoids breaking callers while
        the dashboard catches up to the new evidence model.
        """
        schema = CompanyFacts.model_json_schema()
        cache_key = _hash("scrape-facts-v1", url, json.dumps(schema, sort_keys=True))

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

        self._ensure_budget(self.credits_per_call)

        try:
            facts_json = self._dispatch(url=url, schema=schema)
        except Exception as exc:  # noqa: BLE001
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
        self._record_firecrawl_spend(credits=self.credits_per_call)

        self._write_cache(
            cache_key,
            facts=facts.model_dump(mode="json"),
            credits_used=self.credits_per_call,
        )
        return FirecrawlResult(facts=facts, credits_used=self.credits_per_call, cached=False)

    # -- live dispatch (override-friendly for tests) ---------------------

    def _dispatch(self, *, url: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Make the legacy JSON-mode SDK call."""
        from firecrawl.v2.types import JsonFormat

        formats = [
            "markdown",
            JsonFormat(type="json", prompt=ENRICH_PROMPT, schema=schema),
        ]
        document = self.firecrawl.scrape(url, formats=formats, only_main_content=True)
        if document is None or not getattr(document, "json", None):
            raise RuntimeError("firecrawl returned no json payload")
        return document.json  # type: ignore[no-any-return]

    def _dispatch_map(self, url: str):
        """Call Firecrawl /map and return the SDK result."""
        return self.firecrawl.map(
            url,
            include_subdomains=False,
            ignore_query_parameters=True,
            limit=40,
        )

    def _dispatch_search(self, query: str, *, limit: int, tbs: str):
        """Call Firecrawl /search and return the SDK result."""
        return self.firecrawl.search(query, limit=limit, tbs=tbs)

    def _dispatch_scrape_markdown(self, url: str) -> MarkdownDocument:
        """Scrape one URL in basic markdown mode."""
        document = self.firecrawl.scrape(
            url,
            formats=["markdown"],
            only_main_content=True,
        )
        markdown = getattr(document, "markdown", None)
        if not markdown:
            raise RuntimeError("firecrawl returned no markdown payload")
        metadata = getattr(document, "metadata", None)
        title = getattr(metadata, "title", None) if metadata is not None else None
        return MarkdownDocument(url=url, title=title, markdown=str(markdown))

    # -- internals --------------------------------------------------------

    def _ensure_budget(self, estimated_credits: int) -> None:
        if self.stats.credits_used + estimated_credits > self.budget_credits:
            raise FirecrawlBudgetExceeded(
                f"would exceed {self.budget_credits}-credit cap "
                f"(used {self.stats.credits_used}, next call costs {estimated_credits})"
            )

    def _record_firecrawl_spend(self, *, credits: int) -> None:
        self.stats.calls += 1
        self.stats.credits_used += credits

    def _find_company_pages_unmetered(self, root_url: str) -> list[str]:
        result = self._dispatch_map(root_url)
        links = getattr(result, "links", None) or []
        pages: list[str] = []
        seen: set[str] = set()
        for link in links:
            if isinstance(link, dict):
                url = str(link.get("url") or "")
                title = link.get("title")
            else:
                url = str(getattr(link, "url", "") or "")
                title = getattr(link, "title", None)
            normalised = _normalise_url(url)
            if not normalised or normalised == root_url:
                continue
            if normalised in seen or not _same_domain(root_url, normalised):
                continue
            if not _candidate_page_matches(normalised, str(title) if title else None):
                continue
            pages.append(normalised)
            seen.add(normalised)
            if len(pages) >= MAX_COMPANY_PAGES:
                break
        return pages

    def _fetch_company_news_unmetered(self, *, name: str, limit: int) -> list[MarkdownDocument]:
        query = f'"{name}" founder OR CEO OR raised'
        results = self._dispatch_search(
            query,
            limit=SEARCH_RESULTS_LIMIT,
            tbs=SEARCH_TBS_LAST_YEAR,
        )
        docs: list[MarkdownDocument] = []
        seen: set[str] = set()
        for url in _search_result_urls(results):
            normalised = _normalise_url(url)
            if not normalised or normalised in seen or _is_blocked_news_url(normalised):
                continue
            seen.add(normalised)
            doc = self._safe_scrape_markdown(normalised)
            if doc is not None:
                docs.append(doc)
            if len(docs) >= limit:
                break
        return docs

    def _safe_scrape_markdown(self, url: str) -> MarkdownDocument | None:
        try:
            return self._dispatch_scrape_markdown(url)
        except Exception as exc:  # noqa: BLE001
            self.stats.failures.append(f"{url}: scrape: {type(exc).__name__}: {exc}")
            LOGGER.warning("firecrawl markdown scrape failed for %s: %s", url, exc)
            return None

    def _coerce_facts(self, raw: dict[str, Any]) -> CompanyFacts:
        """Best-effort coercion of the SDK json payload into CompanyFacts."""
        cleaned: dict[str, Any] = dict(raw)

        founded = cleaned.get("founded_year")
        if isinstance(founded, str):
            try:
                cleaned["founded_year"] = int(founded.strip())
            except ValueError:
                cleaned["founded_year"] = None

        for list_field in ("founders", "sector_keywords", "evidence_urls"):
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


def _search_result_urls(results: Any) -> list[str]:
    urls: list[str] = []
    for bucket_name in ("news", "web"):
        bucket = getattr(results, bucket_name, None) or []
        for item in bucket:
            url = getattr(item, "url", None)
            if url:
                urls.append(str(url))
    return urls


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
    """Sanitise user-facing strings and recompute confidence from populated fields."""
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
            "evidence_urls": _dedupe_urls(facts.evidence_urls),
        }
    )


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        normalised = _normalise_url(url)
        if not normalised or normalised in seen:
            continue
        seen.add(normalised)
        out.append(normalised)
    return out


def _build_enrichment_context(name: str, documents: list[MarkdownDocument]) -> str:
    chunks = [f"Company: {name}", "Source excerpts:"]
    for idx, doc in enumerate(documents, start=1):
        markdown = doc.markdown[:MAX_MARKDOWN_CHARS_PER_SOURCE]
        title = f"\nTitle: {doc.title}" if doc.title else ""
        chunks.append(f"\n[{idx}] URL: {doc.url}{title}\nMarkdown:\n{markdown}")
    return "\n".join(chunks)


def _evidence_urls_from(facts: CompanyFacts, documents: list[MarkdownDocument]) -> list[str]:
    available_ordered = _dedupe_urls(
        [_normalise_url(doc.url) for doc in documents if doc.markdown.strip()]
    )
    available = set(available_ordered)
    selected = [
        _normalise_url(url) for url in facts.evidence_urls if _normalise_url(url) in available
    ]
    return _dedupe_urls(selected or available_ordered)


def firecrawl_enrich(
    client: FirecrawlClient,
    llm_client: ClaudeClient,
    website: str | None,
    *,
    name: str,
) -> CompanyFacts:
    """Enrich one company website and recent coverage into CompanyFacts."""
    if not website or not website.strip():
        return CompanyFacts.empty()

    root_url = _normalise_url(website)
    schema_hash = json.dumps(CompanyFacts.model_json_schema(), sort_keys=True)
    cache_key = _hash("enrich-v2", root_url, name, schema_hash)
    cached = client._read_cache(cache_key)
    if cached is not None:
        try:
            facts = CompanyFacts.model_validate(cached["facts"])
        except ValidationError as exc:
            LOGGER.warning(
                "firecrawl enrich cache for %s failed validation: %s", cache_key[:8], exc
            )
        else:
            client.stats.cache_hits += 1
            return facts

    client._ensure_budget(DEFAULT_CREDITS_PER_ENRICH)

    homepage = client._safe_scrape_markdown(root_url)
    try:
        company_pages = client._find_company_pages_unmetered(root_url)[
            :MAX_EXTRA_COMPANY_PAGES_FOR_ENRICH
        ]
    except Exception as exc:  # noqa: BLE001
        client.stats.failures.append(f"{root_url}: map: {type(exc).__name__}: {exc}")
        LOGGER.warning("firecrawl map failed for %s: %s", root_url, exc)
        company_pages = []
    documents: list[MarkdownDocument] = [homepage] if homepage is not None else []
    for page_url in company_pages:
        doc = client._safe_scrape_markdown(page_url)
        if doc is not None:
            documents.append(doc)

    try:
        documents.extend(
            client._fetch_company_news_unmetered(name=name, limit=MAX_NEWS_RESULTS_FOR_ENRICH)
        )
    except Exception as exc:  # noqa: BLE001
        client.stats.failures.append(f"{name}: search: {type(exc).__name__}: {exc}")
        LOGGER.warning("firecrawl search failed for %s: %s", name, exc)
    client._record_firecrawl_spend(credits=DEFAULT_CREDITS_PER_ENRICH)

    if not documents:
        return CompanyFacts.empty()

    try:
        response = llm_client.structured_call(
            system=ENRICH_PROMPT,
            prompt=_build_enrichment_context(name, documents),
            schema_cls=CompanyFacts,
            max_tokens=1024,
        )
    except BudgetExceeded:
        raise
    except Exception as exc:  # noqa: BLE001
        client.stats.failures.append(f"{root_url}: claude enrichment: {type(exc).__name__}: {exc}")
        LOGGER.warning("claude enrichment failed for %s: %s", root_url, exc)
        return CompanyFacts.empty()

    parsed = response.parsed
    if isinstance(parsed, CompanyFacts):
        facts = parsed
    elif isinstance(parsed, BaseModel):
        facts = CompanyFacts.model_validate(parsed.model_dump())
    else:
        facts = CompanyFacts.model_validate(parsed)

    facts = _post_process(facts)
    facts = facts.model_copy(update={"evidence_urls": _evidence_urls_from(facts, documents)})
    client._write_cache(
        cache_key,
        facts=facts.model_dump(mode="json"),
        credits_used=DEFAULT_CREDITS_PER_ENRICH,
    )
    return facts
