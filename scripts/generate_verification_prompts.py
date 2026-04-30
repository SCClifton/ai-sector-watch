#!/usr/bin/env python3
"""Generate per-sector deep-research verification prompts.

Reads verified companies from Supabase, buckets them by sector, and emits one
Markdown prompt per sector (with parts when a sector exceeds the limit). Each
prompt is designed to be run in Gemini Deep Research, ChatGPT Deep Research,
or Perplexity Pro - or driven programmatically by `run_verification_prompts.py`.

Usage:
    op run --env-file=.env.local -- python scripts/generate_verification_prompts.py --write
    op run --env-file=.env.local -- python scripts/generate_verification_prompts.py --sector vertical_legal --write
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.discovery.geocoder import known_cities  # noqa: E402
from ai_sector_watch.discovery.taxonomy import (  # noqa: E402
    SECTOR_GROUPS,
    SECTORS,
    STAGES,
    get_sector,
)
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger("generate_verification_prompts")

PROMPT_TEMPLATE_PATH = REPO_ROOT / "prompts" / "verify_sector.md"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "verification"
DEFAULT_LIMIT_PER_PROMPT = 25

SECTOR_DESCRIPTIONS: dict[str, str] = {
    "foundation_models": "Companies training or fine-tuning their own large language, vision, or multimodal models.",
    "ai_infrastructure": "Compute, model serving, data pipelines, fine-tuning platforms, and other AI substrate.",
    "vector_search_and_retrieval": "Vector databases, embedding pipelines, hybrid search, and retrieval engines.",
    "evals_and_observability": "Evaluation harnesses, prompt and trace observability, model monitoring, and safety testing.",
    "vertical_legal": "AI applied to legal workflows: contract review, e-discovery, litigation, in-house automation.",
    "vertical_healthcare": "AI applied to clinical, diagnostic, medical-imaging, drug-discovery, or digital-health workflows.",
    "vertical_finance": "AI applied to trading, underwriting, fraud, accounting, banking, or wealth.",
    "vertical_sales_marketing": "AI applied to sales prospecting, marketing copy, ad creative, CRM enrichment, or revenue ops.",
    "vertical_security": "AI applied to cyber security: threat detection, fraud, identity, SOC automation.",
    "robotics_industrial": "Industrial robotics: manufacturing, logistics, mining, agriculture, construction.",
    "robotics_autonomous_vehicles": "Autonomous ground or aerial vehicles, ADAS, or self-driving stacks.",
    "robotics_household": "Consumer or service robotics for the home or hospitality.",
    "ai_for_science_biology": "AI for biological discovery: protein, genomics, biotech R&D, lab automation.",
    "ai_for_science_chemistry": "AI for chemistry: materials simulation, reaction prediction, molecular design.",
    "ai_for_science_materials": "AI for materials science: alloys, composites, batteries, semiconductors.",
    "ai_for_climate_energy": "AI applied to climate, decarbonisation, energy markets, grid operations, or sustainability.",
    "defence_and_dual_use": "Defence and dual-use AI: ISR, autonomy, sensing, sovereign capability.",
    "edge_and_on_device": "AI that runs at the edge or on-device: embedded models, optimised inference, hardware-aware tooling.",
    "developer_tools": "Tools for developers building AI products: SDKs, agents-as-code, prompt tooling, IDE assistants.",
    "agents_and_orchestration": "Agentic systems, workflow orchestration, planners, and multi-step automation.",
    "creative_and_media": "Generative creative: text, image, video, audio, music, design, and media production.",
}

# Fields surfaced in the prompt's company block (the "current record").
PROMPT_VISIBLE_FIELDS: tuple[str, ...] = (
    "country",
    "city",
    "website",
    "sector_tags",
    "stage",
    "founded_year",
    "summary",
    "founders",
    "total_raised_usd",
    "total_raised_currency_raw",
    "total_raised_as_of",
    "total_raised_source_url",
    "valuation_usd",
    "valuation_currency_raw",
    "valuation_as_of",
    "valuation_source_url",
    "headcount_estimate",
    "headcount_min",
    "headcount_max",
    "headcount_as_of",
    "headcount_source_url",
    "profile_confidence",
    "profile_verified_at",
)


@dataclass
class GenerateSummary:
    """Operator-facing summary for a generator run."""

    output_dir: str
    write: bool
    sectors_seen: int = 0
    prompts_written: int = 0
    companies_in_prompts: int = 0
    skipped_sectors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _slugify(name: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return name or "company"


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        # Drop trailing zeros for cleaner display.
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list | tuple):
        if not value:
            return "[]"
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    text = str(value)
    if "\n" in text:
        text = " ".join(text.split())
    return text


def _company_yaml_block(company: dict[str, Any]) -> str:
    """Render one company's current record as a yaml-ish block for the prompt."""
    lines = [
        f"- id: {company['id']}",
        f"  name: {_format_value(company.get('name'))}",
    ]
    for field_name in PROMPT_VISIBLE_FIELDS:
        if field_name not in company:
            continue
        value = company.get(field_name)
        if value is None or value == [] or value == "":
            # Show null explicitly so the model knows the field is empty.
            lines.append(f"  {field_name}: null")
            continue
        lines.append(f"  {field_name}: {_format_value(value)}")
    return "\n".join(lines)


def _enum_list(items: list[tuple[str, str]]) -> str:
    return "\n".join(f"- `{tag}` - {label}" for tag, label in items)


def _sector_enum_lines() -> list[tuple[str, str]]:
    return [(s.tag, s.label) for s in SECTORS]


def _stage_enum_lines() -> list[tuple[str, str]]:
    pretty = {
        "pre_seed": "Pre-seed (idea or angel round)",
        "seed": "Seed (institutional seed round)",
        "series_a": "Series A",
        "series_b_plus": "Series B or later",
        "mature": "Mature (revenue-driven, post-Series-C, public, or bootstrapped at scale)",
    }
    return [(stage, pretty.get(stage, stage)) for stage in STAGES]


def _cities_block() -> str:
    return ", ".join(known_cities())


def render_prompt(
    *,
    template: str,
    sector_tag: str,
    sector_label: str,
    sector_group: str,
    sector_description: str,
    companies: list[dict[str, Any]],
) -> str:
    """Render the prompt for a single sector (or sector-part)."""
    company_blocks = "\n\n".join(_company_yaml_block(company) for company in companies)
    replacements = {
        "{{SECTOR_TAG}}": sector_tag,
        "{{SECTOR_LABEL}}": sector_label,
        "{{SECTOR_GROUP}}": sector_group,
        "{{SECTOR_DESCRIPTION}}": sector_description,
        "{{COMPANY_COUNT}}": str(len(companies)),
        "{{COMPANIES_BLOCK}}": company_blocks,
        "{{SECTOR_ENUM_LIST}}": _enum_list(_sector_enum_lines()),
        "{{STAGE_ENUM_LIST}}": _enum_list(_stage_enum_lines()),
        "{{CITIES_LIST}}": _cities_block(),
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def bucket_by_sector(companies: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group companies by sector tag. Multi-tag companies appear in each sector."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for company in companies:
        tags = company.get("sector_tags") or []
        if not tags:
            buckets.setdefault("untagged", []).append(company)
            continue
        for tag in tags:
            buckets.setdefault(tag, []).append(company)
    return buckets


def bucket_by_group(companies: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group companies by sector colour group. A multi-group company appears once per group it touches.

    Companies are de-duplicated within a group so they don't appear twice when
    they have multiple sector tags inside the same group.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    for company in companies:
        tags = company.get("sector_tags") or []
        if not tags:
            buckets.setdefault("untagged", []).append(company)
            continue
        groups_touched: set[str] = set()
        for tag in tags:
            sector = get_sector(tag)
            if sector is None:
                continue
            groups_touched.add(sector.group)
        for group in groups_touched:
            existing = buckets.setdefault(group, [])
            if not any(str(c.get("id")) == str(company.get("id")) for c in existing):
                existing.append(company)
    return buckets


GROUP_LABELS: dict[str, str] = {
    "infra": "AI infrastructure",
    "vertical": "Vertical applications",
    "robotics": "Robotics",
    "science": "AI for science",
    "climate": "Climate and energy",
    "defence": "Defence and dual use",
    "dev_tools": "Developer tools",
    "agents": "Agents and orchestration",
    "creative": "Creative and media",
}

GROUP_DESCRIPTIONS: dict[str, str] = {
    "infra": "Core AI infrastructure: foundation model training, model serving, vector search and retrieval, evaluations and observability, and edge or on-device inference.",
    "vertical": "AI applied to specific industries: legal, healthcare, finance, sales and marketing, security.",
    "robotics": "Robotics across industrial, autonomous-vehicle, and household categories.",
    "science": "AI for scientific discovery: biology, chemistry, materials.",
    "climate": "AI applied to climate, decarbonisation, energy markets, and sustainability.",
    "defence": "Defence and dual-use AI: ISR, autonomy, sensing, sovereign capability.",
    "dev_tools": "Tools for developers building AI products: SDKs, agents-as-code, IDE assistants.",
    "agents": "Agentic systems, workflow orchestration, planners, and multi-step automation.",
    "creative": "Generative creative across text, image, video, audio, music, design, and media production.",
}


def _split_into_parts(
    companies: list[dict[str, Any]],
    *,
    limit_per_prompt: int,
) -> list[list[dict[str, Any]]]:
    if limit_per_prompt <= 0:
        return [companies]
    return [companies[i : i + limit_per_prompt] for i in range(0, len(companies), limit_per_prompt)]


def _prompt_filename(sector_tag: str, *, part: int, parts_total: int) -> str:
    if parts_total <= 1:
        return f"verify_{sector_tag}.md"
    return f"verify_{sector_tag}_part{part}of{parts_total}.md"


def _response_filename(prompt_filename: str) -> str:
    # `verify_<x>.md` -> `verify_<x>.json`
    return Path(prompt_filename).with_suffix(".json").name


def run_generate(
    *,
    output_dir: Path,
    sector_filter: str | None,
    limit_per_prompt: int,
    write: bool,
    bucket_strategy: str = "per-sector",
    companies: list[dict[str, Any]] | None = None,
) -> GenerateSummary:
    """Build and (optionally) write the verification prompts.

    bucket_strategy:
        - "per-sector": one prompt per sector tag (~21 prompts).
        - "per-group": one prompt per sector colour group (9 groups: infra,
          vertical, robotics, science, climate, defence, dev_tools, agents,
          creative). Caps prompt count for manual paste workflows.
    """
    summary = GenerateSummary(output_dir=str(output_dir), write=write)
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    if companies is None:
        with supabase_db.connection() as conn:
            companies = supabase_db.list_companies(conn, statuses=("verified",))

    if bucket_strategy == "per-group":
        buckets = bucket_by_group(companies)
        bucket_order = list(SECTOR_GROUPS) + sorted(
            tag for tag in buckets if tag not in SECTOR_GROUPS
        )
        bucket_label = GROUP_LABELS
        bucket_description = GROUP_DESCRIPTIONS
        bucket_filter = sector_filter
    else:
        buckets = bucket_by_sector(companies)
        bucket_order = [s.tag for s in SECTORS] + sorted(
            tag for tag in buckets if tag not in {s.tag for s in SECTORS}
        )
        bucket_label = {s.tag: s.label for s in SECTORS}
        bucket_description = SECTOR_DESCRIPTIONS
        bucket_filter = sector_filter
    summary.sectors_seen = len(buckets)

    prompts_dir = output_dir / "prompts"
    if write:
        prompts_dir.mkdir(parents=True, exist_ok=True)

    index: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "limit_per_prompt": limit_per_prompt,
        "bucket_strategy": bucket_strategy,
        "prompts": [],
    }

    for bucket_key in bucket_order:
        bucket_companies = buckets.get(bucket_key, [])
        if bucket_filter and bucket_key != bucket_filter:
            continue
        if not bucket_companies:
            summary.skipped_sectors.append(bucket_key)
            continue

        bucket_companies.sort(key=lambda c: str(c.get("name") or "").lower())
        parts = _split_into_parts(bucket_companies, limit_per_prompt=limit_per_prompt)
        for part_index, part_companies in enumerate(parts, start=1):
            prompt_filename = _prompt_filename(bucket_key, part=part_index, parts_total=len(parts))
            response_filename = _response_filename(prompt_filename)
            label = bucket_label.get(bucket_key, bucket_key)
            description = bucket_description.get(bucket_key, "")
            group_for_render = (
                bucket_key
                if bucket_strategy == "per-group"
                else (get_sector(bucket_key).group if get_sector(bucket_key) else "")
            )
            rendered = render_prompt(
                template=template,
                sector_tag=bucket_key,
                sector_label=label,
                sector_group=group_for_render,
                sector_description=description,
                companies=part_companies,
            )
            summary.companies_in_prompts += len(part_companies)
            summary.prompts_written += 1
            index["prompts"].append(
                {
                    "bucket": bucket_key,
                    "label": label,
                    "part": part_index,
                    "parts_total": len(parts),
                    "company_count": len(part_companies),
                    "prompt_path": f"prompts/{prompt_filename}",
                    "response_path": f"responses/{response_filename}",
                    "company_ids": [str(c["id"]) for c in part_companies],
                }
            )
            if write:
                (prompts_dir / prompt_filename).write_text(rendered, encoding="utf-8")

    if bucket_filter and summary.prompts_written == 0:
        summary.errors.append(
            f"bucket filter `{bucket_filter}` matched no verified companies; "
            f"check against the chosen bucket strategy"
        )

    if write:
        (output_dir / "index.json").write_text(
            json.dumps(index, indent=2, sort_keys=False), encoding="utf-8"
        )

    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sector",
        default=None,
        help=(
            "Restrict to one sector tag (per-sector strategy) or one group "
            "(per-group strategy). Defaults to all."
        ),
    )
    parser.add_argument(
        "--bucket-strategy",
        choices=("per-sector", "per-group"),
        default="per-group",
        help=(
            "How to bucket companies across prompts. "
            "per-group (default) bundles by colour group (~9 prompts). "
            "per-sector emits one prompt per sector tag (~21 prompts)."
        ),
    )
    parser.add_argument(
        "--limit-per-prompt",
        type=int,
        default=DEFAULT_LIMIT_PER_PROMPT,
        help="Max companies per prompt; oversized buckets split into part1, part2, ...",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Where to write prompts/, responses/, and index.json.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write prompt files to disk. Default is dry-run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    if args.sector is not None:
        if args.bucket_strategy == "per-sector" and get_sector(args.sector) is None:
            LOGGER.error("unknown sector tag: %s", args.sector)
            return 2
        if args.bucket_strategy == "per-group" and args.sector not in SECTOR_GROUPS:
            LOGGER.error("unknown sector group: %s", args.sector)
            return 2
    if args.limit_per_prompt < 1:
        LOGGER.error("--limit-per-prompt must be a positive integer")
        return 2

    summary = run_generate(
        output_dir=args.output_dir,
        sector_filter=args.sector,
        limit_per_prompt=args.limit_per_prompt,
        write=args.write,
        bucket_strategy=args.bucket_strategy,
    )
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    if summary.errors:
        for error in summary.errors:
            LOGGER.error(error)
        return 1
    if not args.write:
        LOGGER.info("dry run only; rerun with --write to emit prompt files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
