"""Static ANZ city to lat/lon lookup with deterministic jitter for marker overlap."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

ANZ_CITIES: dict[str, tuple[float, float]] = {
    "Sydney": (-33.8688, 151.2093),
    "Melbourne": (-37.8136, 144.9631),
    "Brisbane": (-27.4698, 153.0251),
    "Perth": (-31.9505, 115.8605),
    "Adelaide": (-34.9285, 138.6007),
    "Canberra": (-35.2809, 149.1300),
    "Hobart": (-42.8821, 147.3272),
    "Darwin": (-12.4634, 130.8456),
    "Newcastle": (-32.9283, 151.7817),
    "Gold Coast": (-28.0167, 153.4000),
    "Sunshine Coast": (-26.6500, 153.0667),
    "Wollongong": (-34.4278, 150.8931),
    "Geelong": (-38.1499, 144.3617),
    "Auckland": (-36.8485, 174.7633),
    "Wellington": (-41.2865, 174.7762),
    "Christchurch": (-43.5320, 172.6306),
    "Queenstown": (-45.0312, 168.6626),
    "Dunedin": (-45.8788, 170.5028),
    "Hamilton": (-37.7870, 175.2793),
}

# Country codes the static lookup applies to.
ANZ_COUNTRIES: frozenset[str] = frozenset({"AU", "NZ", "Australia", "New Zealand"})

# Jitter radius in degrees, ~1km at the relevant latitudes. Small enough
# that markers stay visually grouped on the city, big enough to spread
# the icons rather than fully overlapping.
_JITTER_RADIUS_DEG = 0.012


@dataclass(frozen=True)
class GeocodeResult:
    """A lat/lon pair plus the source city name (post-jitter)."""

    lat: float
    lon: float
    city: str
    jittered: bool


def _deterministic_jitter(seed: str) -> tuple[float, float]:
    """Return a stable (dlat, dlon) pair derived from `seed`.

    Same seed -> same jitter, so markers don't move across reloads.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    # Take two bytes per axis, normalise to [-1, 1], scale to jitter radius.
    dlat = ((digest[0] << 8 | digest[1]) / 0xFFFF * 2 - 1) * _JITTER_RADIUS_DEG
    dlon = ((digest[2] << 8 | digest[3]) / 0xFFFF * 2 - 1) * _JITTER_RADIUS_DEG
    return dlat, dlon


def normalise_city(name: str | None) -> str | None:
    """Title-case and strip a city name. Returns None for empty input."""
    if not name:
        return None
    return name.strip().title()


def geocode_city(
    city: str | None,
    *,
    jitter_seed: str | None = None,
) -> GeocodeResult | None:
    """Look up a city in `ANZ_CITIES`, optionally applying a deterministic jitter.

    `jitter_seed` is typically the company name; passing it spreads multiple
    companies that map to the same city without making them move on reload.
    Returns None when the city is unknown.
    """
    name = normalise_city(city)
    if not name or name not in ANZ_CITIES:
        return None
    lat, lon = ANZ_CITIES[name]
    if jitter_seed:
        dlat, dlon = _deterministic_jitter(jitter_seed)
        return GeocodeResult(lat=lat + dlat, lon=lon + dlon, city=name, jittered=True)
    return GeocodeResult(lat=lat, lon=lon, city=name, jittered=False)


def known_cities() -> list[str]:
    """Sorted list of cities supported by the static lookup."""
    return sorted(ANZ_CITIES.keys())
