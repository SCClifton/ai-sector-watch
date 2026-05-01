"""Tests for the deep-research verification response parser."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import parse_verification_responses as p  # noqa: E402


def test_extract_json_array_picks_last_fenced_block() -> None:
    """Worked-example block without an id should be ignored; final answer wins."""
    text = """
# Report

Schema reminder (no id in this demo on purpose):

```json
{"verdict": "update", "updates": {"city": "Sydney"}}
```

## Findings...

```json
[{"id": "real-1", "name": "RealCo", "verdict": "update", "updates": {}}]
```
"""
    result = p._extract_json_array(text)
    assert isinstance(result, list)
    assert result[0]["id"] == "real-1"
    assert len(result) == 1


def test_extract_json_array_repairs_markdown_escapes_and_empty_fields() -> None:
    """Gemini DR sometimes prints JSON outside fences with markdown escapes."""
    text = r"""
Some narrative.

\[
  {
    "id": "company-1",
    "name": "GeminiCo",
    "verdict": "update",
    "updates": {
      "stage": "series\_a",
      "founders":,
      "evidence\_urls":
    },
    "evidence\_urls": \["https://example.com"\],
    "confidence": 0.9
  }
\]
"""
    result = p._extract_json_array(text)
    assert isinstance(result, list)
    assert result[0]["id"] == "company-1"
    assert result[0]["updates"]["stage"] == "series_a"
    # Empty `founders":,` fields became null after repair.
    assert result[0]["updates"]["founders"] is None


def test_extract_json_array_collects_separate_id_bearing_objects() -> None:
    """Some Gemini outputs emit one JSON object per company, not one array."""
    text = """
## Cohort report

```json
{"id": "co-1", "name": "First", "verdict": "update", "updates": {}}
```

```json
{"id": "co-2", "name": "Second", "verdict": "confirm", "updates": {}}
```
"""
    result = p._extract_json_array(text)
    assert isinstance(result, list)
    assert {entry["id"] for entry in result} == {"co-1", "co-2"}


def test_validate_entry_normalises_string_confidence_labels() -> None:
    entry = {
        "id": "co-1",
        "name": "LabelCo",
        "verdict": "update",
        "updates": {"profile_confidence": "high"},
        "evidence_urls": ["https://example.com"],
    }
    parsed, errors = p._validate_entry(entry)
    assert parsed is not None
    assert parsed.updates["profile_confidence"] == 0.9
    # The substitution should be surfaced as a (non-fatal) warning.
    assert any("normalised" in e for e in errors)


def test_validate_entry_drops_unknown_confidence_label() -> None:
    entry = {
        "id": "co-1",
        "name": "WeirdCo",
        "verdict": "update",
        "updates": {"profile_confidence": "VERY VERY HIGH"},
        "evidence_urls": ["https://example.com"],
    }
    parsed, errors = p._validate_entry(entry)
    assert parsed is not None
    assert "profile_confidence" not in parsed.updates
    assert any("not recognised" in e for e in errors)


def test_validate_entry_normalises_flat_schema_to_updates() -> None:
    """A flat-schema entry (every field at the top level) should be promoted."""
    entry = {
        "id": "co-1",
        "name": "FlatCo",
        "city": "Sydney",
        "stage": "seed",
        "founded_year": 2022,
    }
    parsed, errors = p._validate_entry(entry)
    assert parsed is not None
    assert parsed.verdict == "update"
    assert parsed.updates["city"] == "Sydney"
    assert parsed.updates["stage"] == "seed"
    assert parsed.updates["founded_year"] == 2022


def test_run_parse_writes_apply_and_flags_artifacts(tmp_path: Path) -> None:
    responses = tmp_path / "responses"
    responses.mkdir()
    (responses / "verify_x.md").write_text(
        json.dumps(
            [
                {
                    "id": "co-1",
                    "name": "GoodCo",
                    "verdict": "update",
                    "updates": {"city": "Sydney"},
                    "evidence_urls": ["https://example.com"],
                    "confidence": 0.9,
                },
                {
                    "id": "co-2",
                    "name": "BadCo",
                    "verdict": "flag_for_rejection",
                    "evidence_urls": [],
                    "notes": "Defunct.",
                },
            ]
        ),
        encoding="utf-8",
    )

    summary = p.run_parse(input_dir=tmp_path, write=True)
    assert summary.errors == []
    assert summary.entries_seen == 2
    assert summary.by_verdict.get("update") == 1
    assert summary.by_verdict.get("flag_for_rejection") == 1

    apply_payload = json.loads(Path(summary.apply_path).read_text(encoding="utf-8"))
    assert apply_payload["companies"][0]["id"] == "co-1"
    assert apply_payload["companies"][0]["updates"]["city"] == "Sydney"

    flags_payload = json.loads(Path(summary.flags_path).read_text(encoding="utf-8"))
    assert flags_payload["companies"][0]["id"] == "co-2"


def test_run_parse_merges_multi_sector_entries(tmp_path: Path) -> None:
    """Same company id appearing in two responses gets merged."""
    responses = tmp_path / "responses"
    responses.mkdir()
    (responses / "verify_a.md").write_text(
        json.dumps(
            [
                {
                    "id": "shared-co",
                    "name": "SharedCo",
                    "verdict": "update",
                    "updates": {"city": "Sydney"},
                    "evidence_urls": ["https://a.example.com"],
                    "confidence": 0.85,
                }
            ]
        ),
        encoding="utf-8",
    )
    (responses / "verify_b.md").write_text(
        json.dumps(
            [
                {
                    "id": "shared-co",
                    "name": "SharedCo",
                    "verdict": "confirm",
                    "updates": {},
                    "evidence_urls": ["https://b.example.com"],
                    "confidence": 0.9,
                }
            ]
        ),
        encoding="utf-8",
    )

    summary = p.run_parse(input_dir=tmp_path, write=True)
    apply_payload = json.loads(Path(summary.apply_path).read_text(encoding="utf-8"))
    assert len(apply_payload["companies"]) == 1
    merged = apply_payload["companies"][0]
    assert merged["updates"]["city"] == "Sydney"  # update verdict wins over confirm
    # Sources from both responses are unioned.
    assert sorted(merged["evidence_urls"]) == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_run_parse_flags_conflicting_updates(tmp_path: Path) -> None:
    """If two responses give different values for the same field, route to flags."""
    responses = tmp_path / "responses"
    responses.mkdir()
    for idx, city in enumerate(("Sydney", "Melbourne")):
        (responses / f"verify_{idx}.md").write_text(
            json.dumps(
                [
                    {
                        "id": "shared",
                        "name": "Shared",
                        "verdict": "update",
                        "updates": {"city": city},
                        "evidence_urls": [f"https://{idx}.example.com"],
                        "confidence": 0.9,
                    }
                ]
            ),
            encoding="utf-8",
        )

    summary = p.run_parse(input_dir=tmp_path, write=True)
    assert summary.conflicts and "city" in summary.conflicts[0]
    flags_payload = json.loads(Path(summary.flags_path).read_text(encoding="utf-8"))
    assert flags_payload["companies"][0]["verdict"] == "flag_for_review"
