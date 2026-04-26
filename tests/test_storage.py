"""Tests for the Supabase storage layer.

Pure-Python helpers run in every test session. Live-DB integration tests
auto-skip unless `SUPABASE_DB_URL` is exported in the environment.
"""

from __future__ import annotations

import os

import pytest

from ai_sector_watch.storage import supabase_db
from ai_sector_watch.storage.supabase_db import (
    compute_payload_hash,
    hash_url,
    load_schema_sql,
    normalise_name,
)

# ----- Pure-Python helpers ---------------------------------------------------


def test_compute_payload_hash_is_deterministic() -> None:
    a = compute_payload_hash({"b": 2, "a": 1})
    b = compute_payload_hash({"a": 1, "b": 2})
    assert a == b
    assert len(a) == 64  # SHA256 hex


def test_compute_payload_hash_distinguishes_payloads() -> None:
    assert compute_payload_hash({"a": 1}) != compute_payload_hash({"a": 2})


def test_hash_url_deterministic_and_url_specific() -> None:
    assert hash_url("https://example.com/a") == hash_url("https://example.com/a")
    assert hash_url("https://example.com/a") != hash_url("https://example.com/b")


def test_normalise_name_lowercase_and_collapses_whitespace() -> None:
    assert normalise_name("  Marqo  ") == "marqo"
    assert normalise_name("Relevance   AI") == "relevance ai"
    assert normalise_name("Harrison.AI") == "harrison.ai"


def test_load_schema_sql_contains_core_tables() -> None:
    sql = load_schema_sql()
    for table in ("companies", "funding_events", "news_items", "ingest_events"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, (
            f"schema is missing {table}"
        )
    assert "discovery_status" in sql
    assert "company_stage" in sql


def test_get_conn_raises_when_supabase_db_url_unset(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    with pytest.raises(KeyError):
        supabase_db._get_db_url()


# ----- Live integration tests (skipped without SUPABASE_DB_URL) --------------

pytestmark_live = pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL not set; skipping live integration tests",
)


@pytestmark_live
def test_live_apply_schema_then_upsert_company_round_trip() -> None:
    """Full round-trip: apply schema, upsert a company, read it back, clean up."""
    from ai_sector_watch.storage.supabase_db import (
        apply_schema,
        connection,
        get_company_by_name,
        upsert_company,
    )

    test_name = "AI Sector Watch Test Co"
    with connection() as conn:
        apply_schema(conn)
        company_id = upsert_company(
            conn,
            name=test_name,
            country="AU",
            city="Sydney",
            lat=-33.87,
            lon=151.21,
            sector_tags=["foundation_models"],
            stage="seed",
            discovery_status="verified",
            discovery_source="test",
        )
        conn.commit()
        row = get_company_by_name(conn, test_name, "AU")
        assert row is not None
        assert row["name"] == test_name
        assert row["sector_tags"] == ["foundation_models"]
        # Idempotent: a second upsert returns the same id.
        company_id_2 = upsert_company(
            conn,
            name=test_name,
            country="AU",
            sector_tags=["foundation_models"],
            stage="seed",
            discovery_status="verified",
            discovery_source="test",
        )
        assert company_id == company_id_2
        # Clean up.
        with conn.cursor() as cur:
            cur.execute("DELETE FROM companies WHERE id = %s", (company_id,))
        conn.commit()
