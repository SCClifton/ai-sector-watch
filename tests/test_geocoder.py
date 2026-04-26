"""Tests for the static ANZ city geocoder."""

from __future__ import annotations

import pytest

from ai_sector_watch.discovery.geocoder import (
    ANZ_CITIES,
    geocode_city,
    known_cities,
    normalise_city,
)


def test_known_city_returns_exact_coords_without_jitter() -> None:
    result = geocode_city("Sydney")
    assert result is not None
    assert result.city == "Sydney"
    assert result.jittered is False
    assert (result.lat, result.lon) == ANZ_CITIES["Sydney"]


def test_unknown_city_returns_none() -> None:
    assert geocode_city("Atlantis") is None


def test_empty_or_none_input_returns_none() -> None:
    assert geocode_city(None) is None
    assert geocode_city("") is None
    assert geocode_city("   ") is None


def test_lowercase_and_padded_city_normalises() -> None:
    result = geocode_city("  melbourne  ")
    assert result is not None
    assert result.city == "Melbourne"


def test_jitter_offsets_within_radius_and_is_deterministic() -> None:
    base = geocode_city("Sydney")
    a = geocode_city("Sydney", jitter_seed="Marqo")
    b = geocode_city("Sydney", jitter_seed="Marqo")
    c = geocode_city("Sydney", jitter_seed="Relevance AI")
    assert base is not None and a is not None and b is not None and c is not None
    # Jittered point sits near the base, never on top of it.
    assert a.jittered is True
    assert (a.lat, a.lon) != (base.lat, base.lon)
    assert abs(a.lat - base.lat) < 0.05
    assert abs(a.lon - base.lon) < 0.05
    # Same seed -> same point.
    assert (a.lat, a.lon) == (b.lat, b.lon)
    # Different seed -> different point.
    assert (a.lat, a.lon) != (c.lat, c.lon)


@pytest.mark.parametrize(
    "city",
    [
        "Sydney",
        "Auckland",
        "Wellington",
        "Brisbane",
        "Hobart",
        "Queenstown",
    ],
)
def test_all_anz_capitals_and_priority_cities_known(city: str) -> None:
    assert geocode_city(city) is not None


def test_known_cities_is_sorted() -> None:
    cities = known_cities()
    assert cities == sorted(cities)
    assert "Sydney" in cities
    assert "Auckland" in cities


def test_normalise_city_idempotent() -> None:
    assert normalise_city("sydney") == "Sydney"
    assert normalise_city(normalise_city("sydney")) == "Sydney"
