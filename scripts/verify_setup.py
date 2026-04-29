#!/usr/bin/env python3
"""Smoke checks for AI Sector Watch local + Supabase + secret state.

Usage:
    op run --env-file=.env.local -- python scripts/verify_setup.py
    op run --env-file=.env.local -- python scripts/verify_setup.py --apply-schema

Exits non-zero if any required check FAILs. WARN does not affect exit code.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import get_config  # noqa: E402
from ai_sector_watch.storage import supabase_db  # noqa: E402


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS" | "WARN" | "FAIL"
    detail: str


def _result(name: str, ok: bool, detail: str, *, warn: bool = False) -> CheckResult:
    if ok:
        return CheckResult(name, "PASS", detail)
    return CheckResult(name, "WARN" if warn else "FAIL", detail)


def check_python_version() -> CheckResult:
    ok = sys.version_info >= (3, 12) and sys.version_info < (3, 14)
    return _result(
        "Python 3.12.x",
        ok,
        f"running {sys.version.split()[0]}",
    )


def check_anthropic_key() -> CheckResult:
    cfg = get_config()
    ok = bool(cfg.anthropic_api_key)
    return _result(
        "ANTHROPIC_API_KEY",
        ok,
        "set" if ok else "not set (required for pipeline)",
        warn=not ok,  # not strictly required for dashboard-only work
    )


def check_admin_password() -> CheckResult:
    cfg = get_config()
    ok = bool(cfg.admin_password)
    return _result(
        "ADMIN_PASSWORD",
        ok,
        "set" if ok else "not set (required for /Admin page)",
        warn=not ok,
    )


def check_digest_dir() -> CheckResult:
    cfg = get_config()
    cfg.digest_output_dir.mkdir(parents=True, exist_ok=True)
    return _result("digest output dir", True, str(cfg.digest_output_dir))


def check_supabase_url_set() -> CheckResult:
    set_ok = bool(os.environ.get("SUPABASE_DB_URL"))
    return _result(
        "SUPABASE_DB_URL",
        set_ok,
        "set" if set_ok else "not set",
    )


def check_supabase_connect() -> CheckResult:
    if not os.environ.get("SUPABASE_DB_URL"):
        return _result("Supabase connect", False, "skipped: SUPABASE_DB_URL unset", warn=True)
    try:
        with supabase_db.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()
            assert row and row["ok"] == 1
        return _result("Supabase connect", True, "SELECT 1 ok")
    except Exception as exc:  # noqa: BLE001
        return _result("Supabase connect", False, f"{type(exc).__name__}: {exc}")


def check_supabase_schema(apply: bool) -> CheckResult:
    if not os.environ.get("SUPABASE_DB_URL"):
        return _result("Supabase schema", False, "skipped: SUPABASE_DB_URL unset", warn=True)
    try:
        with supabase_db.connection() as conn:
            if apply:
                supabase_db.apply_schema(conn)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) AS n FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN
                        ('companies', 'funding_events', 'news_items', 'ingest_events')
                    """)
                row = cur.fetchone()
        n = row["n"] if row else 0
        ok = n == 4
        return _result(
            "Supabase schema",
            ok,
            f"{n}/4 tables present" + (" (after --apply-schema)" if apply else ""),
            warn=not ok and not apply,
        )
    except Exception as exc:  # noqa: BLE001
        return _result("Supabase schema", False, f"{type(exc).__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Apply src/ai_sector_watch/storage/supabase_schema.sql to Supabase",
    )
    args = parser.parse_args()

    checks = [
        check_python_version(),
        check_anthropic_key(),
        check_admin_password(),
        check_digest_dir(),
        check_supabase_url_set(),
        check_supabase_connect(),
        check_supabase_schema(apply=args.apply_schema),
    ]

    width = max(len(c.name) for c in checks)
    for c in checks:
        marker = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[c.status]
        print(f"[{marker}] {c.name:<{width}}  {c.detail}")

    fails = [c for c in checks if c.status == "FAIL"]
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
