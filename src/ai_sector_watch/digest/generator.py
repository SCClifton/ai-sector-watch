"""Markdown digest writer for the weekly pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ai_sector_watch.config import get_config


@dataclass(frozen=True)
class DigestNewsRow:
    title: str
    url: str
    source_slug: str
    kind: str
    company_names: list[str]


@dataclass(frozen=True)
class DigestStats:
    sources_attempted: int
    sources_ok: int
    items_seen: int
    items_new: int
    candidates_added: int
    cost_usd: float


def write_digest(
    *,
    run_date: date,
    stats: DigestStats,
    new_companies: list[str],
    news: Iterable[DigestNewsRow],
    output_dir: Path | None = None,
) -> Path:
    """Render this run's digest as markdown and return the path written."""
    cfg = get_config()
    out_dir = output_dir or cfg.digest_output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run_date.isoformat()}.md"

    lines: list[str] = []
    lines.append(f"# Weekly digest, {run_date.isoformat()}")
    lines.append("")
    lines.append(
        f"Generated at {datetime.now().isoformat(timespec='seconds')}. "
        f"Auto-extracted from public sources by AI Sector Watch."
    )
    lines.append("")
    lines.append("## Pipeline summary")
    lines.append("")
    lines.append(f"- Sources attempted: {stats.sources_attempted}")
    lines.append(f"- Sources OK: {stats.sources_ok}")
    lines.append(f"- News items seen: {stats.items_seen}")
    lines.append(f"- News items new this run: {stats.items_new}")
    lines.append(f"- New candidate companies surfaced: {stats.candidates_added}")
    lines.append(f"- Estimated LLM cost this run: ${stats.cost_usd:.4f}")
    lines.append("")
    if new_companies:
        lines.append("## New candidate companies (pending admin review)")
        lines.append("")
        for name in sorted(new_companies):
            lines.append(f"- {name}")
        lines.append("")
    news_list = list(news)
    if news_list:
        lines.append("## Relevant news")
        lines.append("")
        for row in news_list:
            mention_str = (
                f" — mentions: {', '.join(row.company_names)}" if row.company_names else ""
            )
            lines.append(
                f"- [{row.title}]({row.url}) ({row.source_slug}, {row.kind}){mention_str}"
            )
        lines.append("")

    path.write_text("\n".join(lines).replace("—", " - "), encoding="utf-8")
    return path
