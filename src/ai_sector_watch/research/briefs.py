"""Build structured daily frontier-AI research brief runs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from ai_sector_watch.sources import arxiv_source
from ai_sector_watch.sources.base import RawItem, SourceBase
from ai_sector_watch.sources.huggingface_papers import HuggingFacePapers

ResearchItemType = Literal[
    "paper",
    "artifact",
    "lab_update",
    "benchmark",
    "model_card",
    "system_card",
    "dataset",
    "code",
    "watchlist",
]

SECTION_KEYS = (
    "top_items",
    "papers_worth_reading",
    "research_artifacts",
    "lab_company_updates",
    "watchlist",
)

FRONTIER_KEYWORDS: tuple[str, ...] = (
    "agent",
    "alignment",
    "benchmark",
    "chain-of-thought",
    "code",
    "dataset",
    "diffusion",
    "evaluation",
    "frontier",
    "inference",
    "large language",
    "llm",
    "long context",
    "memory",
    "model",
    "multimodal",
    "post-training",
    "reasoning",
    "reinforcement learning",
    "robotics",
    "safety",
    "scaling",
    "tool use",
    "transformer",
    "vision-language",
)


@dataclass(frozen=True)
class ResearchBriefItem:
    """One primary-source item shown in a public research brief."""

    title: str
    source_lab: str
    item_type: ResearchItemType
    published_at: str | None
    primary_url: str
    secondary_urls: list[str] = field(default_factory=list)
    takeaway: str = ""
    why_it_matters: str = ""
    evidence_quality: str = "Primary source"
    limitations: str = ""


@dataclass(frozen=True)
class ResearchBriefSections:
    """Section payload stored as JSONB for the public site."""

    top_items: list[ResearchBriefItem] = field(default_factory=list)
    papers_worth_reading: list[ResearchBriefItem] = field(default_factory=list)
    research_artifacts: list[ResearchBriefItem] = field(default_factory=list)
    lab_company_updates: list[ResearchBriefItem] = field(default_factory=list)
    watchlist: list[ResearchBriefItem] = field(default_factory=list)
    skipped_noise_note: str = ""


@dataclass(frozen=True)
class ResearchBriefRun:
    """Database and JSON shape for one research brief run."""

    id: str
    run_date: str
    window_start: str
    window_end: str
    title: str
    summary: str
    sections: ResearchBriefSections
    sources: list[dict[str, Any]]
    cost_usd: float | None = None
    model: str | None = None
    status: str = "published"
    created_at: str | None = None
    updated_at: str | None = None


def default_research_sources() -> list[SourceBase]:
    """Return primary research sources for daily brief generation."""
    return [
        arxiv_source.arxiv_cs_ai(),
        arxiv_source.arxiv_cs_lg(),
        arxiv_source.arxiv_cs_cl(),
        arxiv_source.arxiv_cs_cv(),
        arxiv_source.arxiv_cs_ro(),
        HuggingFacePapers(),
    ]


def build_research_brief_run(
    *,
    raw_items: list[RawItem],
    run_date: date,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    source_errors: list[str] | None = None,
) -> ResearchBriefRun:
    """Convert fetched source items into a structured public run."""
    end = window_end or datetime.combine(
        run_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC
    )
    start = window_start or end - timedelta(hours=36)
    source_errors = source_errors or []
    windowed = [
        item
        for item in raw_items
        if item.published_at is None or start <= item.published_at.astimezone(UTC) <= end
    ]
    ranked = sorted(_dedupe_items(windowed), key=_score_item, reverse=True)
    top_items = [_brief_item(item) for item in ranked[:5]]
    papers = [_brief_item(item) for item in ranked[:12]]
    artifacts = [
        _brief_item(item)
        for item in ranked
        if _classify_item_type(item)
        in {"benchmark", "dataset", "code", "model_card", "system_card"}
    ][:8]
    watchlist = [_brief_item(item, item_type="watchlist") for item in ranked[12:20]]
    skipped_count = max(len(windowed) - len(ranked[:20]), 0)
    skipped_note = _skipped_note(
        fetched_count=len(raw_items),
        window_count=len(windowed),
        shown_count=len(
            {item.primary_url for item in [*top_items, *papers, *artifacts, *watchlist]}
        ),
        skipped_count=skipped_count,
        source_errors=source_errors,
    )
    sections = ResearchBriefSections(
        top_items=top_items,
        papers_worth_reading=papers,
        research_artifacts=artifacts,
        lab_company_updates=[],
        watchlist=watchlist,
        skipped_noise_note=skipped_note,
    )
    summary = _summary(run_date=run_date, window_count=len(windowed), ranked_count=len(ranked))
    source_rows = sorted(
        {
            (
                item.source_slug,
                _source_label(item.source_slug),
            )
            for item in raw_items
        }
    )
    return ResearchBriefRun(
        id=str(uuid5(NAMESPACE_URL, f"ai-sector-watch:research:{run_date.isoformat()}")),
        run_date=run_date.isoformat(),
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        title=f"Research: {run_date.isoformat()}",
        summary=summary,
        sections=sections,
        sources=[{"slug": slug, "label": label} for slug, label in source_rows],
        cost_usd=None,
        model=None,
        status="published",
    )


def research_run_to_dict(run: ResearchBriefRun) -> dict[str, Any]:
    """Return a JSON-serialisable run payload."""
    return asdict(run)


def write_research_run_json(run: ResearchBriefRun, directory: Path) -> Path:
    """Write a run JSON file keyed by run date."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run.run_date}.json"
    path.write_text(
        json.dumps(research_run_to_dict(run), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _dedupe_items(items: list[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    result: list[RawItem] = []
    for item in items:
        key = _primary_url(item).lower() or item.title.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _brief_item(item: RawItem, *, item_type: ResearchItemType | None = None) -> ResearchBriefItem:
    clean_summary = _clean_text(item.summary)
    published_at = item.published_at.astimezone(UTC).isoformat() if item.published_at else None
    primary_url = _primary_url(item)
    secondary_urls = [url for url in [item.url] if url != primary_url]
    return ResearchBriefItem(
        title=_clean_text(item.title),
        source_lab=_source_label(item.source_slug),
        item_type=item_type or _classify_item_type(item),
        published_at=published_at,
        primary_url=primary_url,
        secondary_urls=secondary_urls,
        takeaway=_takeaway(item.title, clean_summary),
        why_it_matters=_why_it_matters(item.title, clean_summary),
        evidence_quality=_evidence_quality(item),
        limitations=_limitations(item),
    )


def _primary_url(item: RawItem) -> str:
    arxiv_id = item.raw.get("arxiv_id")
    if isinstance(arxiv_id, str) and arxiv_id.strip():
        return f"https://arxiv.org/abs/{arxiv_id.strip()}"
    return item.url


def _classify_item_type(item: RawItem) -> ResearchItemType:
    text = f"{item.title} {item.summary or ''}".lower()
    if "system card" in text:
        return "system_card"
    if "model card" in text:
        return "model_card"
    if "dataset" in text or "corpus" in text:
        return "dataset"
    if "benchmark" in text or "evaluation" in text or "eval" in text:
        return "benchmark"
    if "github" in text or "code" in text or "repository" in text:
        return "code"
    return "paper"


def _score_item(item: RawItem) -> float:
    text = f"{item.title} {item.summary or ''}".lower()
    score = 0.0
    for keyword in FRONTIER_KEYWORDS:
        if keyword in text:
            score += 2.0 if keyword in item.title.lower() else 1.0
    if item.source_slug == "huggingface_papers":
        score += min(float(item.raw.get("upvotes") or 0) / 10.0, 5.0)
    if item.published_at:
        age_hours = max(
            (datetime.now(UTC) - item.published_at.astimezone(UTC)).total_seconds() / 3600,
            0,
        )
        score += max(3.0 - (age_hours / 24.0), 0.0)
    return score


def _source_label(source_slug: str) -> str:
    labels = {
        "arxiv_cs_ai": "arXiv cs.AI",
        "arxiv_cs_lg": "arXiv cs.LG",
        "arxiv_cs_cl": "arXiv cs.CL",
        "arxiv_cs_cv": "arXiv cs.CV",
        "arxiv_cs_ro": "arXiv cs.RO",
        "huggingface_papers": "Hugging Face Daily Papers",
    }
    return labels.get(source_slug, source_slug.replace("_", " ").title())


def _takeaway(title: str, summary: str) -> str:
    if summary:
        return _clip(summary, 190)
    return f"Primary-source research item: {_clean_text(title)}."


def _why_it_matters(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if "benchmark" in text or "evaluation" in text or "eval" in text:
        return "Adds evidence for comparing frontier model capability or reliability."
    if "agent" in text or "tool" in text:
        return "Relevant to agentic systems, tool use, and applied AI workflows."
    if "multimodal" in text or "vision" in text or "speech" in text:
        return "Relevant to multimodal model capability and product surfaces."
    if "safety" in text or "alignment" in text:
        return "Relevant to frontier model risk, governance, and deployment quality."
    if "robot" in text:
        return "Relevant to embodied AI and robotics capability."
    return "Relevant to frontier AI capability, infrastructure, or evaluation."


def _evidence_quality(item: RawItem) -> str:
    if item.source_slug.startswith("arxiv_"):
        return "Primary preprint metadata from arXiv."
    if item.source_slug == "huggingface_papers":
        return "Primary paper link surfaced through Hugging Face Daily Papers."
    return "Primary source metadata."


def _limitations(item: RawItem) -> str:
    if item.source_slug.startswith("arxiv_"):
        return "Preprint status; claims may not be peer reviewed."
    if item.source_slug == "huggingface_papers":
        return "Ranking reflects Hugging Face metadata and automated filtering."
    return "Automated filtering; inspect the source before relying on claims."


def _summary(*, run_date: date, window_count: int, ranked_count: int) -> str:
    if ranked_count == 0:
        return (
            f"No primary-source frontier AI items were selected for {run_date.isoformat()} "
            "after the filter pass."
        )
    return (
        f"Reviewed {window_count} primary-source research items for "
        f"{run_date.isoformat()} and selected the strongest papers and artifacts."
    )


def _skipped_note(
    *,
    fetched_count: int,
    window_count: int,
    shown_count: int,
    skipped_count: int,
    source_errors: list[str],
) -> str:
    parts = [
        f"Fetched {fetched_count} items; {window_count} were in the time window; {shown_count} are shown."
    ]
    if skipped_count:
        parts.append(f"Skipped {skipped_count} lower-ranked or duplicate items.")
    if source_errors:
        parts.append(f"{len(source_errors)} source fetches failed and were skipped.")
    return " ".join(parts)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = " ".join(value.replace("\n", " ").replace("\r", " ").split())
    return re.sub(
        r"^arXiv:\S+\s+Announce Type:\s+\S+\s+Abstract:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )


def _clip(value: str, limit: int) -> str:
    value = _clean_text(value)
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."
