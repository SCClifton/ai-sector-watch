"""Folium map of companies with clustering and sector-coloured markers."""

from __future__ import annotations

from decimal import Decimal
from html import escape

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

# Folium renders the map (and its leaflet popups) inside an iframe, so the
# dashboard's parent stylesheet does not reach them. Mirror the design tokens
# from docs/design-system.md here and inject once per map.
_POPUP_CSS: str = """
.leaflet-popup-content-wrapper {
  background: #121821 !important;
  color: #E6EDF3 !important;
  border-radius: 6px !important;
  border: 1px solid #222B3B !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4) !important;
}
.leaflet-popup-tip {
  background: #121821 !important;
  border: 1px solid #222B3B !important;
}
.leaflet-popup-close-button { color: #8B95A6 !important; }
.aisw-popup {
  --aisw-text: #E6EDF3;
  --aisw-text-muted: #8B95A6;
  --aisw-border: #222B3B;
  --aisw-accent: #F4B740;
  --aisw-accent-hover: #FFD074;
  --aisw-accent-soft: rgba(244, 183, 64, 0.12);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  color: var(--aisw-text);
}
.aisw-popup__title { font-weight: 600; font-size: 14px; }
.aisw-popup__title a { color: var(--aisw-accent); text-decoration: none; }
.aisw-popup__title a:hover { color: var(--aisw-accent-hover); }
.aisw-popup__meta {
  color: var(--aisw-text-muted);
  font-size: 12px;
  margin-top: 2px;
}
.aisw-popup__row { margin-top: 4px; }
.aisw-popup__row em { font-style: normal; color: var(--aisw-text-muted); }
.aisw-popup__chips {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.aisw-popup__chip {
  background: var(--aisw-accent-soft);
  color: var(--aisw-accent);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  letter-spacing: 0.02em;
}
.aisw-popup__summary {
  margin-top: 8px;
  line-height: 1.45;
  color: var(--aisw-text);
}
"""


def build_map(companies: list[Company]) -> folium.Map:
    """Build a folium map with one clustered marker per company that has coords."""
    fmap = folium.Map(
        location=_DEFAULT_CENTER,
        zoom_start=_DEFAULT_ZOOM,
        tiles="cartodbpositron",
        control_scale=True,
    )
    fmap.get_root().header.add_child(folium.Element(f"<style>{_POPUP_CSS}</style>"))
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
    """Render the per-marker popup with design-system tokens."""
    sector_labels = []
    for tag in c.sector_tags:
        sector = get_sector(tag)
        sector_labels.append(sector.label if sector else tag)

    parts: list[str] = ['<div class="aisw-popup">']
    name_html = escape(c.name)
    if c.website:
        name_html = (
            f'<a href="{escape(c.website)}" target="_blank" '
            f'rel="noopener noreferrer">{escape(c.name)}</a>'
        )
    parts.append(f'<div class="aisw-popup__title">{name_html}</div>')

    location_bits = [escape(b) for b in (c.city, c.country) if b]
    if location_bits:
        parts.append(f'<div class="aisw-popup__meta">{", ".join(location_bits)}</div>')

    if c.stage:
        parts.append(f'<div class="aisw-popup__row"><em>Stage:</em> {escape(c.stage)}</div>')
    if c.founded_year:
        parts.append(f'<div class="aisw-popup__row"><em>Founded:</em> {c.founded_year}</div>')

    funding_line = _latest_funding_line(c)
    if funding_line:
        parts.append(
            f'<div class="aisw-popup__row"><em>Latest funding:</em> {escape(funding_line)}</div>'
        )
    total_raised = _format_amount_usd(c.total_raised_usd)
    if total_raised:
        parts.append(f'<div class="aisw-popup__row"><em>Total raised:</em> {total_raised}</div>')
    valuation = _format_amount_usd(c.valuation_usd)
    if valuation:
        parts.append(f'<div class="aisw-popup__row"><em>Valuation:</em> {valuation}</div>')
    headcount = _headcount_line(c)
    if headcount:
        parts.append(f'<div class="aisw-popup__row"><em>Headcount:</em> {escape(headcount)}</div>')

    if sector_labels:
        chips = "".join(
            f'<span class="aisw-popup__chip">{escape(label)}</span>' for label in sector_labels
        )
        parts.append(f'<div class="aisw-popup__chips">{chips}</div>')

    if c.summary:
        parts.append(f'<div class="aisw-popup__summary">{escape(c.summary)}</div>')

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
    if amount >= Decimal("1000000000"):
        billions = amount / Decimal("1000000000")
        value = f"{billions:.1f}".rstrip("0").rstrip(".")
        return f"US${value}B"
    if amount >= Decimal("1000000"):
        millions = amount / Decimal("1000000")
        value = f"{millions:.1f}".rstrip("0").rstrip(".")
        return f"US${value}M"
    if amount >= Decimal("1000"):
        thousands = amount / Decimal("1000")
        value = f"{thousands:.1f}".rstrip("0").rstrip(".")
        return f"US${value}K"
    return f"US${amount:,.0f}"


def _headcount_line(c: Company) -> str | None:
    if c.headcount_estimate is not None:
        return str(c.headcount_estimate)
    if c.headcount_min is not None and c.headcount_max is not None:
        return f"{c.headcount_min}-{c.headcount_max}"
    if c.headcount_min is not None:
        return f"{c.headcount_min}+"
    if c.headcount_max is not None:
        return f"up to {c.headcount_max}"
    return None


def split_geocoded(companies: list[Company]) -> tuple[list[Company], list[Company]]:
    """Return `(with_coords, without_coords)` so the page can show a stat."""
    with_coords = [c for c in companies if c.lat is not None and c.lon is not None]
    without = [c for c in companies if c not in with_coords]
    return with_coords, without
