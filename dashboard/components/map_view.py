"""Folium map of companies with clustering and sector-coloured markers."""

from __future__ import annotations

from decimal import Decimal

import folium
from folium.plugins import MarkerCluster

from ai_sector_watch.discovery.taxonomy import (
    get_sector,
    primary_sector_colour,
)
from ai_sector_watch.storage.data_source import Company

# Map view defaults: centred over the south-east of the continent so Sydney,
# Melbourne, and Auckland all sit on screen at default zoom.
_DEFAULT_CENTER = (-32.0, 151.5)
_DEFAULT_ZOOM = 4
_STAGE_LABELS = {
    "pre_seed": "Pre-seed",
    "seed": "Seed",
    "series_a": "Series A",
    "series_b_plus": "Series B+",
    "mature": "Mature",
}


def build_map(companies: list[Company]) -> folium.Map:
    """Build a folium map with one clustered marker per company that has coords."""
    fmap = folium.Map(
        location=_DEFAULT_CENTER,
        zoom_start=_DEFAULT_ZOOM,
        tiles="cartodbpositron",
        control_scale=True,
    )
    cluster = MarkerCluster(name="Companies", show=True).add_to(fmap)

    geocoded = 0
    for company in companies:
        if company.lat is None or company.lon is None:
            continue
        geocoded += 1
        colour = primary_sector_colour(company.sector_tags)
        folium.Marker(
            location=(company.lat, company.lon),
            icon=folium.Icon(color=colour, icon="info-sign"),
            popup=folium.Popup(_popup_html(company), max_width=320),
            tooltip=company.name,
        ).add_to(cluster)

    folium.LayerControl(collapsed=True).add_to(fmap)
    return fmap


def _popup_html(c: Company) -> str:
    """Render the per-marker popup. No em dashes (PRD section 16)."""
    sector_labels = []
    for tag in c.sector_tags:
        sector = get_sector(tag)
        sector_labels.append(sector.label if sector else tag)

    parts: list[str] = ['<div style="font-family: sans-serif; font-size: 13px;">']
    name_html = c.name
    if c.website:
        name_html = f'<a href="{c.website}" target="_blank" rel="noopener noreferrer">{c.name}</a>'
    parts.append(f"<div><strong>{name_html}</strong></div>")

    location_bits = [b for b in (c.city, c.country) if b]
    if location_bits:
        parts.append(f'<div style="color:#555">{", ".join(location_bits)}</div>')

    if c.stage:
        parts.append(f'<div style="margin-top:4px;"><em>Stage:</em> {c.stage}</div>')
    if c.founded_year:
        parts.append(f"<div><em>Founded:</em> {c.founded_year}</div>")

    funding_line = _latest_funding_line(c)
    if funding_line:
        parts.append(f'<div style="margin-top:4px;"><em>Latest funding:</em> {funding_line}</div>')

    if sector_labels:
        chips = " ".join(
            f'<span style="background:#eef;border-radius:6px;padding:1px 6px;'
            f'margin-right:4px;font-size:11px;">{label}</span>'
            for label in sector_labels
        )
        parts.append(f'<div style="margin-top:6px;">{chips}</div>')

    if c.summary:
        parts.append(f'<div style="margin-top:8px; line-height:1.35;">{c.summary}</div>')

    parts.append("</div>")
    return "".join(parts)


def _latest_funding_line(c: Company) -> str | None:
    event = c.latest_funding_event
    if event is None:
        return None
    bits: list[str] = []
    if event.stage:
        bits.append(_STAGE_LABELS.get(event.stage, event.stage.replace("_", " ").title()))
    if event.announced_on:
        bits.append(event.announced_on.isoformat())
    amount = _format_amount_usd(event.amount_usd)
    if amount:
        bits.append(amount)
    return ", ".join(bits) if bits else None


def _format_amount_usd(amount: Decimal | None) -> str | None:
    if amount is None:
        return None
    if amount >= Decimal("1000000"):
        millions = amount / Decimal("1000000")
        value = f"{millions:.1f}".rstrip("0").rstrip(".")
        return f"US${value}M"
    if amount >= Decimal("1000"):
        thousands = amount / Decimal("1000")
        value = f"{thousands:.1f}".rstrip("0").rstrip(".")
        return f"US${value}K"
    return f"US${amount:,.0f}"


def split_geocoded(companies: list[Company]) -> tuple[list[Company], list[Company]]:
    """Return `(with_coords, without_coords)` so the page can show a stat."""
    with_coords = [c for c in companies if c.lat is not None and c.lon is not None]
    without = [c for c in companies if c not in with_coords]
    return with_coords, without
