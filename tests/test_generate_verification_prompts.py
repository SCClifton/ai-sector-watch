"""Tests for the deep-research verification prompt generator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import generate_verification_prompts as g  # noqa: E402


def _company(
    cid: str, name: str, *, sector_tags: list[str], country: str = "AU"
) -> dict[str, object]:
    return {
        "id": cid,
        "name": name,
        "sector_tags": sector_tags,
        "country": country,
        "discovery_status": "verified",
    }


def test_bucket_by_sector_keeps_multi_tag_companies_in_each_bucket() -> None:
    companies = [
        _company("1", "OnlyLegal", sector_tags=["vertical_legal"]),
        _company("2", "MultiTag", sector_tags=["vertical_legal", "ai_infrastructure"]),
    ]

    buckets = g.bucket_by_sector(companies)

    assert {c["name"] for c in buckets["vertical_legal"]} == {"OnlyLegal", "MultiTag"}
    assert {c["name"] for c in buckets["ai_infrastructure"]} == {"MultiTag"}


def test_bucket_by_group_dedupes_within_a_group() -> None:
    """A company with two sector tags in the SAME group should appear once."""
    companies = [
        _company("1", "MultiInGroup", sector_tags=["vertical_legal", "vertical_finance"]),
        _company("2", "CrossGroup", sector_tags=["vertical_legal", "ai_infrastructure"]),
    ]

    buckets = g.bucket_by_group(companies)

    vertical_names = [c["name"] for c in buckets["vertical"]]
    assert vertical_names.count("MultiInGroup") == 1
    assert vertical_names.count("CrossGroup") == 1
    assert [c["name"] for c in buckets["infra"]] == ["CrossGroup"]


def test_render_prompt_contains_company_record_and_enums() -> None:
    template = (REPO_ROOT / "prompts" / "verify_sector.md").read_text(encoding="utf-8")
    companies = [
        _company("uuid-1", "ExampleCo", sector_tags=["vertical_legal"]),
    ]

    rendered = g.render_prompt(
        template=template,
        sector_tag="vertical_legal",
        sector_label="Legal",
        sector_group="vertical",
        sector_description="Legal AI workflows.",
        companies=companies,
    )

    assert "ExampleCo" in rendered
    assert "uuid-1" in rendered
    assert "Sydney" in rendered  # cities list rendered
    assert "vertical_legal" in rendered  # sector enum rendered
    assert "series_b_plus" in rendered  # stage enum rendered
    # No leftover placeholder syntax
    assert "{{" not in rendered and "}}" not in rendered


def test_run_generate_per_group_writes_one_prompt_per_group(tmp_path: Path) -> None:
    companies = [
        _company("1", "InfraCo", sector_tags=["ai_infrastructure"]),
        _company("2", "RoboCo", sector_tags=["robotics_industrial"]),
        _company("3", "MultiCo", sector_tags=["vertical_legal", "ai_infrastructure"]),
    ]

    summary = g.run_generate(
        output_dir=tmp_path,
        sector_filter=None,
        limit_per_prompt=25,
        write=True,
        bucket_strategy="per-group",
        companies=companies,
    )

    assert summary.errors == []
    assert summary.prompts_written == 3  # infra, vertical, robotics
    written = sorted(p.name for p in (tmp_path / "prompts").iterdir())
    assert "verify_infra.md" in written
    assert "verify_vertical.md" in written
    assert "verify_robotics.md" in written

    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["bucket_strategy"] == "per-group"
    infra_prompt = next(p for p in index["prompts"] if p["bucket"] == "infra")
    assert infra_prompt["company_count"] == 2  # InfraCo + MultiCo


def test_run_generate_dry_run_writes_no_files(tmp_path: Path) -> None:
    companies = [_company("1", "InfraCo", sector_tags=["ai_infrastructure"])]

    summary = g.run_generate(
        output_dir=tmp_path,
        sector_filter=None,
        limit_per_prompt=25,
        write=False,
        bucket_strategy="per-group",
        companies=companies,
    )

    assert summary.prompts_written == 1
    assert not (tmp_path / "prompts").exists()
    assert not (tmp_path / "index.json").exists()


def test_run_generate_splits_oversized_buckets(tmp_path: Path) -> None:
    companies = [_company(str(i), f"Co{i}", sector_tags=["ai_infrastructure"]) for i in range(7)]

    summary = g.run_generate(
        output_dir=tmp_path,
        sector_filter="infra",
        limit_per_prompt=3,
        write=True,
        bucket_strategy="per-group",
        companies=companies,
    )

    assert summary.prompts_written == 3  # 7 cos / 3 per prompt -> 3 parts (3,3,1)
    written = sorted(p.name for p in (tmp_path / "prompts").iterdir())
    assert written == [
        "verify_infra_part1of3.md",
        "verify_infra_part2of3.md",
        "verify_infra_part3of3.md",
    ]
