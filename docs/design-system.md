# Design system

The visual foundation for the AI Sector Watch dashboard. Every page inherits these tokens via [`dashboard/components/theme.py`](../dashboard/components/theme.py); no page should redefine palette, type, or spacing.

**Last updated:** 2026-04-28

---

## How it ships

| Layer | File | Sets |
|---|---|---|
| Streamlit theme | [.streamlit/config.toml](../.streamlit/config.toml) | base, primaryColor, background, font |
| Custom CSS | [dashboard/static/styles.css](../dashboard/static/styles.css) | tokens, typography, components, map popup, dataframe |
| Page chrome helper | [dashboard/components/theme.py](../dashboard/components/theme.py) | `set_page_config` + CSS injection + OG meta + sidebar nav + wordmark |
| Favicon | [dashboard/static/favicon.png](../dashboard/static/favicon.png) | 32x32 PNG, "AI" glyph in accent gold |
| OG image | [dashboard/static/og-image.png](../dashboard/static/og-image.png) | 1200x630 PNG, screenshot of the live map page |

Every page calls `render_page_chrome(title=..., page_icon=...)` at the top instead of `st.set_page_config(...)` directly. That single call lays down the full chrome.

---

## Palette

Dark base. One accent. The accent is reserved for: active state, primary buttons, link hover, the brand wordmark middle word, and the favicon glyph. Everything else is greyscale.

| Token | Hex | Use |
|---|---|---|
| `--aisw-bg` | `#0B0F14` | Page background |
| `--aisw-surface` | `#121821` | Sidebar, cards, dataframe body |
| `--aisw-surface-2` | `#1B2230` | Secondary buttons, table headers, hover |
| `--aisw-border` | `#222B3B` | Default 1px borders |
| `--aisw-border-strong` | `#2C384D` | Inputs, primary buttons |
| `--aisw-text` | `#E6EDF3` | Body text, headings |
| `--aisw-text-muted` | `#8B95A6` | Captions, metric labels, table headers |
| `--aisw-text-subtle` | `#5C6675` | Footer, attributions |
| `--aisw-accent` | `#F4B740` | Primary action, active state, links on hover |
| `--aisw-accent-hover` | `#FFD074` | Accent hover state |
| `--aisw-accent-soft` | `rgba(244,183,64,0.12)` | Multiselect chips, accent backgrounds |
| `--aisw-success` | `#3DDC84` | Verified / promote |
| `--aisw-warning` | `#F4B740` | Aliases accent (intentional: warnings double as draws-the-eye) |
| `--aisw-error` | `#F47171` | Reject / destructive |

Contrast: text on `--aisw-bg` clears WCAG AA (`#E6EDF3` on `#0B0F14` is 14.7:1; `#8B95A6` on `#0B0F14` is 6.7:1). Accent on bg is 9.8:1 (large text only when used on body).

## Typography

**Family:** Inter, loaded via Google Fonts in [`styles.css`](../dashboard/static/styles.css). Fallback stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif`. Code: JetBrains Mono.

**Type scale:**

| Role | Size | Weight | Line-height | Tracking |
|---|---|---|---|---|
| h1 | 32px (2rem) | 700 | 1.2 | 0 |
| h2 | 22px (1.375rem) | 600 | 1.3 | 0 |
| h3 | 17px (1.0625rem) | 600 | 1.4 | 0 |
| Body | 15px (0.9375rem) | 400 | 1.65 | 0 |
| Caption | 13px (0.8125rem) | 400 | 1.5 | 0 |
| Metric label | 12px (0.75rem) | 500 | 1.25 | 0 uppercase |
| Wordmark title | 16.8px (1.05rem) | 600 | 1 | 0 |
| Wordmark tag | 11.5px (0.72rem) | 500 | 1 | 0 uppercase |

Inter is rendered with `font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11'` for the alternate single-storey `a` and straighter digits, which read as more editorial.

## Spacing

Power-of-two scale, used for padding, margin, and gap.

| Token | Pixels |
|---|---|
| `space-1` | 4 |
| `space-2` | 8 |
| `space-3` | 16 |
| `space-4` | 24 |
| `space-5` | 32 |
| `space-6` | 48 |

The main `block-container` is capped at `max-width: 1280px` with `2.5rem` top padding and `4rem` bottom padding. Mobile overrides at `<= 480px` collapse top padding and shrink h1/h2/metrics for sanity at 390px.

## Radius

Square-ish, restrained. No fully rounded corners. No drop shadows.

| Token | Pixels | Use |
|---|---|---|
| `--aisw-radius-sm` | 4 | Tags, chips |
| `--aisw-radius` | 6 | Buttons, inputs, dataframe |
| `--aisw-radius-lg` | 8 | Containers, metric cards |

## Wordmark

Rendered once per page by `render_page_chrome`. Plain text, no logo file:

```
AI Sector Watch    ANZ AI ECOSYSTEM
^^                  ^^^^^^^^^^^^^^^
text-primary        text-subtle uppercase
   ^^^^^^
   accent gold
```

The middle word, "Sector", is set in accent gold. The right-aligned tag in subtle uppercase acts as a section label without competing with page titles.

## Favicon

32x32 PNG with the letters "AI" set in `--aisw-accent` on `--aisw-bg`, rounded corners, generated with Pillow at 4x supersample for clean edges. The 16x16 sibling is generated alongside but not currently linked from `set_page_config` (Streamlit only takes one icon). Regeneration is manual; commit the PNG, not the script.

## OG image

1200x630 PNG screenshot of the rendered map page in this theme. Crawlers fetch it from `https://aimap.cliftonfamily.co/app/static/og-image.png`. Streamlit static serving (`enableStaticServing = true` in `config.toml`) makes the path resolvable.

When the map ships meaningful pin density, refresh the OG image: load the map page in Chrome at 1200x630, take a screenshot, save to `dashboard/static/og-image.png`, commit.

---

## Decision log

### Why dark base

A live ecosystem map is an editorial-research artefact, not a marketing site. Dark base:
- Keeps map tiles, charts, and dataframes the visually loudest objects on the page (they should be).
- Reads as "tool", not "brochure".
- Lets the single accent colour carry actual signal weight without competing with three other warm UI tones.

The risk is low-information dark dashboards that feel like every B2B SaaS app from 2022. We mitigate with confident hierarchy, generous line-height, and zero gradients or drop shadows.

### Why this accent

`#F4B740`, a warm signal gold. Chosen over the obvious tech-default cyan/electric-blue because:
- It's distinct from any of the obvious nearby brand palettes (OpenAI green, Anthropic terracotta, Stripe purple, Linear violet, Vercel monochrome, every fintech blue).
- Editorial connotation: it's the colour of a highlighter underline in a research note. That maps directly to what this dashboard does (highlight ANZ AI activity).
- Strong enough to function as the only accent. Cyan/lime have to fight to read as "primary"; warm gold owns that role on a deep blue-black surface.
- AA contrast against `--aisw-bg` for non-body roles (links on hover, button surfaces, active state).

Not amber or yellow-green. Specifically a warm, slightly-desaturated gold that pairs with a cool-leaning blue-black to create a small temperature contrast.

### Why Inter

- Free and ubiquitous, served by Google Fonts CDN. No licensing or self-hosted-font headache for a public site.
- The Inter weight ramp (400 / 500 / 600 / 700) is rendered identically across browsers, which the Streamlit default sans-serif stack cannot promise.
- Tabular figures by default, which matters for dataframes and metric cards.
- The `cv02 / cv03 / cv04 / cv11` stylistic alternates give us a single-storey `a` and straighter `1`, which read as more editorial.

The runner-up was IBM Plex Sans. Plex carries strong corporate-IBM connotation; Inter is more neutral and the choice is reversible inside `styles.css` if we change our minds.

### Why no drop shadows or gradients

These signal "consumer SaaS marketing". This dashboard signals "research artefact". The contrast tools we use are: 1px borders, surface elevation via colour (`bg` -> `surface` -> `surface-2`), and the single accent. That's it.

### Why a brand wordmark instead of a logo file

V1 ships text only. A logo file is a separate design exercise that needs more iteration than the rest of this issue warrants. Text wordmark with the middle word accented carries the same recognition role at zero design debt and zero asset to maintain.

---

## Known limitations

- `st.dataframe` link cells render through Glide Data Grid's canvas, not the DOM. CSS overrides do not reach them, so link cells display in the upstream blue. The `column_config.LinkColumn` rendering is fixed upstream; if Streamlit exposes a token for this, wire it up.

## Extending the system

When adding a new component:
1. Reach for the existing tokens before introducing a new colour or radius.
2. If a new token is genuinely required, add it to the `:root` block in [`styles.css`](../dashboard/static/styles.css), then document it here.
3. Do not introduce a second accent colour. If you need to differentiate two states, vary `--aisw-accent-soft` opacity or borrow from `--aisw-success` / `--aisw-error`.
4. No drop shadows, no gradients, no chrome.
