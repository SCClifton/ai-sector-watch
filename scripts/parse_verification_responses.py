#!/usr/bin/env python3
"""Parse deep-research verification responses into apply-ready artifacts.

Reads JSON responses produced by Gemini Deep Research / ChatGPT Deep Research
(saved into `data/verification/responses/`), validates them against the apply
script's allowed fields, merges per-company verdicts (multi-sector companies
appear in more than one response), and writes:

  - `apply_<timestamp>.json` for `scripts/apply_company_profile_updates.py`
  - `flags_<timestamp>.json` for human triage in /Admin

Usage:
    python scripts/parse_verification_responses.py
    python scripts/parse_verification_responses.py --input data/verification --write
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import apply_company_profile_updates as apply_updates  # noqa: E402

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.discovery.geocoder import known_cities  # noqa: E402
from ai_sector_watch.discovery.taxonomy import SECTOR_TAGS, STAGES  # noqa: E402

LOGGER = logging.getLogger("parse_verification_responses")

DEFAULT_INPUT_DIR = REPO_ROOT / "data" / "verification"
ALLOWED_FIELDS = apply_updates.ALLOWED_UPDATE_FIELDS
VALID_VERDICTS = {"confirm", "update", "flag_for_review", "flag_for_rejection"}
EM_DASH_PATTERN = re.compile(r"\s*[—–]\s*")  # em/en dashes with surrounding whitespace
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)

# Gemini DR sometimes emits profile_confidence as a string label rather than a
# float. Map the common labels onto sensible mid-band floats so the apply does
# not blow up on the numeric column.
CONFIDENCE_LABEL_MAP: dict[str, float] = {
    "high": 0.9,
    "medium": 0.7,
    "low": 0.4,
}


@dataclass
class CompanyEntry:
    """One per-company verdict, validated and ready for downstream use."""

    id: str
    name: str
    verdict: str
    updates: dict[str, Any] = field(default_factory=dict)
    evidence_urls: list[str] = field(default_factory=list)
    confidence: float | None = None
    notes: str = ""
    source_files: list[str] = field(default_factory=list)


@dataclass
class ParseSummary:
    """Operator-facing summary for a parser run."""

    input_dir: str
    write: bool
    files_seen: int = 0
    files_failed: list[str] = field(default_factory=list)
    entries_seen: int = 0
    by_verdict: dict[str, int] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    apply_path: str | None = None
    flags_path: str | None = None
    errors: list[str] = field(default_factory=list)


def _balanced_json_substring(text: str, opener: str, closer: str) -> str | None:
    """Return the substring from the LAST balanced opener..closer in `text`.

    Walks the text with a depth counter that ignores brackets inside JSON strings
    (handles escaped quotes). Tries each candidate from the rightmost opener back,
    returning the first that parses. Returns None if no balanced substring is
    found.
    """
    in_string = False
    escape = False
    depth = 0
    starts: list[int] = []
    spans: list[tuple[int, int]] = []
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == opener:
            if depth == 0:
                starts.append(i)
            depth += 1
        elif ch == closer and depth > 0:
            depth -= 1
            if depth == 0 and starts:
                spans.append((starts[-1], i + 1))
    # Try the latest balanced span first - DR reports place the answer last.
    for start, end in reversed(spans):
        candidate = text[start:end]
        try:
            json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return candidate
    return None


_MARKDOWN_ESCAPE_PATTERN = re.compile(r"\\([_\[\]+\-.()#<>|~!*&])")
_EMPTY_VALUE_PATTERN = re.compile(r'("\w+"\s*:)\s*([,}\]])')


def _repair_markdown_json(text: str) -> str:
    """Strip common markdown escapes Gemini DR sprinkles inside JSON.

    Gemini Deep Research outputs the answer JSON as plain text (no fences),
    inside which it markdown-escapes underscores, brackets, plus signs etc.,
    and emits empty values as `"key":,` instead of `"key": null,`. This
    function repairs both so json.loads can take it.
    """
    repaired = _MARKDOWN_ESCAPE_PATTERN.sub(r"\1", text)
    # `"key":,` -> `"key": null,` ; `"key":}` -> `"key": null}` ; `"key":]` likewise.
    repaired = _EMPTY_VALUE_PATTERN.sub(r"\1 null\2", repaired)
    # Strip trailing whitespace per line (markdown line-break artifacts).
    repaired = "\n".join(line.rstrip() for line in repaired.splitlines())
    return repaired


def _collect_id_bearing_objects(text: str) -> list[dict[str, Any]]:
    """Find every balanced {..} in text that parses to a dict with an 'id' key.

    Used when Deep Research emits one JSON object per company instead of a single
    top-level array.
    """
    in_string = False
    escape = False
    depth = 0
    starts: list[int] = []
    objects: list[dict[str, Any]] = []
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                starts.append(i)
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and starts:
                start = starts[-1]
                candidate = text[start : i + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict) and "id" in parsed:
                    objects.append(parsed)
    return objects


def _extract_json_array(text: str) -> Any:
    """Pull the JSON array or object out of a response text blob.

    Strategy, in order:
      1. The whole text is JSON.
      2. The LAST fenced ```json (or ```) block whose body parses.
      3. The LAST balanced [...] in the text whose body parses.
      4. The LAST balanced {...} in the text whose body parses.
      5. Repeat 1-4 after repairing markdown-escaped JSON (Gemini DR style).

    Deep-research reports usually include a worked example mid-document and the
    real answer at the end, so we prefer late occurrences.
    """
    # Try repaired text first - Gemini DR almost always needs the repair, and
    # raw text often contains an empty `[]` from a markdown link that would
    # short-circuit extraction with a useless empty array.
    candidates_in_order = [_repair_markdown_json(text), text]
    last_error: Exception = ValueError("no JSON array or object found in response")
    best_payload: Any = None
    seen_text: set[str] = set()
    for source in candidates_in_order:
        if source in seen_text:
            continue
        seen_text.add(source)
        stripped = source.strip()
        try:
            payload = json.loads(stripped)
            best_payload = _prefer_richer(best_payload, payload)
        except json.JSONDecodeError as exc:
            last_error = exc

        fence_matches = list(JSON_FENCE_PATTERN.finditer(source))
        for match in reversed(fence_matches):
            body = match.group(1).strip()
            try:
                payload = json.loads(body)
                best_payload = _prefer_richer(best_payload, payload)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue

        for opener, closer in (("[", "]"), ("{", "}")):
            candidate = _balanced_json_substring(source, opener, closer)
            if candidate is not None:
                try:
                    payload = json.loads(candidate)
                    best_payload = _prefer_richer(best_payload, payload)
                except json.JSONDecodeError as exc:
                    last_error = exc

        # Multi-object collection - Gemini sometimes emits one JSON per company.
        objects = _collect_id_bearing_objects(source)
        if objects:
            best_payload = _prefer_richer(best_payload, objects)

    if best_payload is None:
        raise ValueError(f"no JSON array or object found in response: {last_error}")
    return best_payload


def _prefer_richer(current: Any, candidate: Any) -> Any:
    """Prefer the payload that looks like the real verification answer.

    Heuristics:
      - A list with company-shaped dicts (have an "id" key) wins.
      - Among lists, more entries with "id" wins.
      - A non-empty list beats an empty list or a non-list.
      - A dict with company shape beats a non-company-shaped value.
    """

    def score(payload: Any) -> tuple[int, int, int]:
        if isinstance(payload, list):
            with_id = sum(1 for item in payload if isinstance(item, dict) and "id" in item)
            return (2 if with_id else (1 if payload else 0), with_id, len(payload))
        if isinstance(payload, dict):
            return (2 if "id" in payload else 1, 1 if "id" in payload else 0, 1)
        return (0, 0, 0)

    if current is None:
        return candidate
    return candidate if score(candidate) > score(current) else current


def _load_response_file(path: Path) -> list[dict[str, Any]]:
    """Load one response file and return a list of company entries."""
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = _extract_json_array(raw)
    else:
        payload = _extract_json_array(raw)
    if isinstance(payload, dict):
        # Permit either {"companies": [...]} or a single company object.
        if "companies" in payload and isinstance(payload["companies"], list):
            return payload["companies"]
        return [payload]
    if not isinstance(payload, list):
        raise ValueError("response payload must be a list of company entries")
    return payload


def _normalize_flat_schema(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a flat-schema entry to the {verdict, updates} shape.

    Some Gemini outputs emit the full company record at the top level (with
    every field directly on the entry, no nested `updates`). Promote any
    ALLOWED_FIELDS values found at top level into `updates` and default the
    verdict to `update`.
    """
    if entry.get("verdict") in VALID_VERDICTS or "updates" in entry:
        return entry
    flat_updates = {k: v for k, v in entry.items() if k in ALLOWED_FIELDS and v is not None}
    if not flat_updates:
        return entry
    promoted = {k: v for k, v in entry.items() if k not in ALLOWED_FIELDS}
    promoted["verdict"] = "update"
    promoted["updates"] = flat_updates
    return promoted


def _validate_entry(entry: dict[str, Any]) -> tuple[CompanyEntry | None, list[str]]:
    """Validate one entry. Returns the parsed entry plus per-entry errors."""
    entry = _normalize_flat_schema(entry)
    errors: list[str] = []
    company_id = entry.get("id")
    name = str(entry.get("name") or "")
    if not company_id or not isinstance(company_id, str):
        return None, [f"entry missing id (name={name!r})"]
    label = f"{name} ({company_id})"
    verdict = entry.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append(f"{label}: invalid verdict {verdict!r}")
        verdict = "flag_for_review"

    updates_raw = entry.get("updates") or {}
    if not isinstance(updates_raw, dict):
        errors.append(f"{label}: updates must be an object, got {type(updates_raw).__name__}")
        updates_raw = {}

    updates: dict[str, Any] = {}
    for key, value in updates_raw.items():
        if key not in ALLOWED_FIELDS:
            errors.append(f"{label}: unsupported field {key!r}")
            continue
        if value is None:
            continue
        if key == "summary" and isinstance(value, str) and EM_DASH_PATTERN.search(value):
            errors.append(
                f"{label}: summary contains em/en dash; replace with colon, comma, or ' - '"
            )
            value = EM_DASH_PATTERN.sub(" - ", value)
        if key == "stage" and value not in STAGES:
            errors.append(f"{label}: invalid stage {value!r}")
            continue
        if key == "city" and value not in known_cities():
            errors.append(f"{label}: city {value!r} not in supported list; flagging")
            verdict = "flag_for_review"
            continue
        if key == "sector_tags":
            if not isinstance(value, list) or not value:
                errors.append(f"{label}: sector_tags must be a non-empty list")
                continue
            unknown = [tag for tag in value if tag not in SECTOR_TAGS]
            if unknown:
                errors.append(f"{label}: unknown sector tags {unknown}")
                continue
            if len(value) > 4:
                errors.append(f"{label}: sector_tags exceeds 4 entries; truncating")
                value = value[:4]
        if key.endswith("_as_of") and isinstance(value, str) and not ISO_DATE_PATTERN.match(value):
            errors.append(f"{label}: {key} must be ISO YYYY-MM-DD, got {value!r}")
            continue
        if key == "profile_confidence" and isinstance(value, str):
            mapped = CONFIDENCE_LABEL_MAP.get(value.strip().lower())
            if mapped is None:
                errors.append(
                    f"{label}: profile_confidence label {value!r} not recognised; dropping"
                )
                continue
            errors.append(f"{label}: profile_confidence {value!r} normalised to {mapped}")
            value = mapped
        updates[key] = value

    evidence_urls = entry.get("evidence_urls") or []
    if not isinstance(evidence_urls, list):
        errors.append(f"{label}: evidence_urls must be a list")
        evidence_urls = []

    if verdict == "update" and updates and not evidence_urls:
        errors.append(f"{label}: verdict=update requires at least one evidence_urls entry")

    confidence = entry.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
            if not 0.0 <= confidence <= 1.0:
                errors.append(f"{label}: confidence {confidence} outside [0, 1]")
                confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            errors.append(f"{label}: confidence not numeric")
            confidence = None

    parsed = CompanyEntry(
        id=str(company_id),
        name=name,
        verdict=verdict,
        updates=updates,
        evidence_urls=[str(u) for u in evidence_urls],
        confidence=confidence,
        notes=str(entry.get("notes") or ""),
    )
    return parsed, errors


def _merge_entries(entries: list[CompanyEntry]) -> tuple[CompanyEntry, list[str]]:
    """Merge multiple verdicts for the same company id. Returns merged entry + conflicts."""
    if len(entries) == 1:
        return entries[0], []
    # Verdict precedence: rejection > review > update > confirm.
    precedence = {
        "flag_for_rejection": 3,
        "flag_for_review": 2,
        "update": 1,
        "confirm": 0,
    }
    chosen = max(entries, key=lambda e: precedence.get(e.verdict, 0))
    merged_updates: dict[str, Any] = {}
    conflicts: list[str] = []
    for entry in entries:
        for key, value in entry.updates.items():
            if key in merged_updates and merged_updates[key] != value:
                conflicts.append(
                    f"{entry.id} ({entry.name}): conflicting {key} across responses "
                    f"({merged_updates[key]!r} vs {value!r}); flagging for review"
                )
            else:
                merged_updates[key] = value
    if conflicts:
        chosen = CompanyEntry(
            id=chosen.id,
            name=chosen.name,
            verdict="flag_for_review",
            updates={},  # do not auto-apply when responses conflict
            evidence_urls=sorted({u for e in entries for u in e.evidence_urls}),
            confidence=chosen.confidence,
            notes=(chosen.notes + "\n\n" + "\n".join(conflicts)).strip(),
            source_files=sorted({f for e in entries for f in e.source_files}),
        )
        return chosen, conflicts
    chosen.updates = merged_updates
    chosen.evidence_urls = sorted({u for e in entries for u in e.evidence_urls})
    chosen.source_files = sorted({f for e in entries for f in e.source_files})
    return chosen, []


def _emit_apply_payload(entries: list[CompanyEntry]) -> dict[str, Any]:
    """Shape an apply_*.json payload from update verdicts."""
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "companies": [
            {
                "id": entry.id,
                "name": entry.name,
                "discovery_status": "verified",
                "updates": {
                    **entry.updates,
                    **(
                        {"profile_sources": entry.evidence_urls}
                        if entry.evidence_urls and "profile_sources" not in entry.updates
                        else {}
                    ),
                    **(
                        {"profile_confidence": entry.confidence}
                        if entry.confidence is not None
                        and "profile_confidence" not in entry.updates
                        else {}
                    ),
                },
                "evidence_urls": entry.evidence_urls,
                "source_files": entry.source_files,
            }
            for entry in entries
        ],
    }


def _emit_flags_payload(entries: list[CompanyEntry]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "companies": [
            {
                "id": entry.id,
                "name": entry.name,
                "verdict": entry.verdict,
                "notes": entry.notes,
                "evidence_urls": entry.evidence_urls,
                "confidence": entry.confidence,
                "source_files": entry.source_files,
            }
            for entry in entries
        ],
    }


def _emit_confirm_payload(entries: list[CompanyEntry]) -> dict[str, Any]:
    """Confirms still bump profile_verified_at + profile_confidence; treat as updates."""
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "companies": [
            {
                "id": entry.id,
                "name": entry.name,
                "discovery_status": "verified",
                "updates": {
                    **({"profile_sources": entry.evidence_urls} if entry.evidence_urls else {}),
                    **(
                        {"profile_confidence": entry.confidence}
                        if entry.confidence is not None
                        else {}
                    ),
                },
                "evidence_urls": entry.evidence_urls,
                "source_files": entry.source_files,
            }
            for entry in entries
        ],
    }


def run_parse(
    *,
    input_dir: Path,
    write: bool,
    timestamp: datetime | None = None,
) -> ParseSummary:
    """Read all response files under input_dir/responses/, validate, and emit artifacts."""
    summary = ParseSummary(input_dir=str(input_dir), write=write)
    responses_dir = input_dir / "responses"
    if not responses_dir.is_dir():
        summary.errors.append(f"responses directory not found: {responses_dir}")
        return summary

    response_files = sorted(p for p in responses_dir.iterdir() if p.is_file())
    if not response_files:
        summary.errors.append(f"no response files in {responses_dir}")
        return summary

    by_id: dict[str, list[CompanyEntry]] = defaultdict(list)
    for path in response_files:
        summary.files_seen += 1
        try:
            entries = _load_response_file(path)
        except Exception as exc:  # noqa: BLE001
            summary.files_failed.append(f"{path.name}: {exc}")
            LOGGER.error("failed to parse %s: %s", path.name, exc)
            continue
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                summary.files_failed.append(
                    f"{path.name}: expected object entries, got {type(raw_entry).__name__}"
                )
                continue
            parsed, entry_errors = _validate_entry(raw_entry)
            for error in entry_errors:
                LOGGER.warning("%s: %s", path.name, error)
            if parsed is None:
                continue
            parsed.source_files = [path.name]
            by_id[parsed.id].append(parsed)
            summary.entries_seen += 1

    merged: list[CompanyEntry] = []
    for entries in by_id.values():
        chosen, conflicts = _merge_entries(entries)
        merged.append(chosen)
        summary.conflicts.extend(conflicts)

    counts: Counter[str] = Counter(entry.verdict for entry in merged)
    summary.by_verdict = dict(counts)

    timestamp = timestamp or datetime.now(UTC)
    stem = timestamp.strftime("%Y%m%dT%H%M%SZ")

    update_entries = [e for e in merged if e.verdict == "update" and e.updates]
    flag_entries = [e for e in merged if e.verdict in {"flag_for_review", "flag_for_rejection"}]
    confirm_entries = [e for e in merged if e.verdict == "confirm"]

    apply_payload = _emit_apply_payload(update_entries)
    flags_payload = _emit_flags_payload(flag_entries)
    confirm_payload = _emit_confirm_payload(confirm_entries)

    if write:
        if update_entries:
            apply_path = input_dir / f"apply_{stem}.json"
            apply_path.write_text(
                json.dumps(apply_payload, indent=2, sort_keys=False), encoding="utf-8"
            )
            summary.apply_path = str(apply_path)
        if flag_entries:
            flags_path = input_dir / f"flags_{stem}.json"
            flags_path.write_text(
                json.dumps(flags_payload, indent=2, sort_keys=False), encoding="utf-8"
            )
            summary.flags_path = str(flags_path)
        if confirm_entries:
            confirm_path = input_dir / f"confirm_{stem}.json"
            confirm_path.write_text(
                json.dumps(confirm_payload, indent=2, sort_keys=False), encoding="utf-8"
            )

    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Input dir containing a `responses/` subdir with deep-research JSON files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write apply_*.json, flags_*.json, confirm_*.json. Default is dry-run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    summary = run_parse(input_dir=args.input, write=args.write)
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    if summary.errors:
        for error in summary.errors:
            LOGGER.error(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
