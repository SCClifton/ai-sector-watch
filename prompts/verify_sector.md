# Verify ANZ AI startup records — sector: {{SECTOR_LABEL}}

You are verifying records in the AI Sector Watch database, a public ecosystem map of Australian and New Zealand AI startups (https://aimap.cliftonfamily.co). For each company below, confirm or correct each field against authoritative web sources, then return a single JSON array as specified at the bottom of this prompt.

## Sector context

- Sector tag: `{{SECTOR_TAG}}`
- Sector label: {{SECTOR_LABEL}}
- Group: {{SECTOR_GROUP}}

In-scope companies are: headquartered in Australia or New Zealand, AI-focused (AI is core to the product, not a buzzword), and currently operating. Out-of-scope companies should be returned with verdict `flag_for_rejection`.

## Companies to verify ({{COMPANY_COUNT}})

{{COMPANIES_BLOCK}}

## Fields to verify

For each company, check every field against authoritative public sources. Prefer in this order: the company's own site (about, team, press), official press releases, established business press (AFR, SmartCompany, ITNews, Crunchbase News, NZ Herald, Stuff), and Crunchbase/Pitchbook profiles where available.

### Free-form fields

- `website` (URL of the canonical product site, not a redirect or social profile)
- `country` (must be `AU` or `NZ`; flag for rejection if neither)
- `city` (must be one of the supported cities below, else flag for review)
- `summary` (one paragraph, max 80 words, no em dashes — use a colon, comma, or " - " instead)
- `founded_year` (integer)
- `founders` (array of full names; only people who founded the company)
- `total_raised_usd` (cumulative external funding in USD; convert from raw currency)
- `total_raised_currency_raw` (e.g. `"AUD 12M"` as reported)
- `total_raised_as_of` (ISO date the figure was reported, e.g. `2024-11-12`)
- `total_raised_source_url` (URL of the report)
- `valuation_usd`, `valuation_currency_raw`, `valuation_as_of`, `valuation_source_url` (same shape as funding)
- `headcount_estimate` (integer, single number) OR `headcount_min` and `headcount_max` (when only a range is reported, e.g. LinkedIn band)
- `headcount_as_of` (ISO date)
- `headcount_source_url`

### Constrained fields (must use exact values from these lists)

**`sector_tags`** — pick 1 to 4 tags from this list. Most relevant first:

{{SECTOR_ENUM_LIST}}

**`stage`** — pick exactly one:

{{STAGE_ENUM_LIST}}

**`city`** — pick one of these supported ANZ cities, or set to `null` and use `verdict: "flag_for_review"` if the company is in a city not on this list:

{{CITIES_LIST}}

## Hard rules

1. **Cite every changed field.** Add the supporting URL to `evidence_urls`. Funding figures must additionally have `*_source_url` populated and `*_as_of` (the date the figure was reported, not today).
2. **No guessing.** If a fact cannot be verified from a source, omit it from `updates` (do not include the key).
3. **No em dashes** anywhere in `summary`. Replace with a colon, comma, or " - ".
4. **Confirm vs update.** If every current field already matches the public record, return `verdict: "confirm"` with empty `updates`. If anything changed, return `verdict: "update"` with only the changed fields in `updates`.
5. **Flag for rejection** (`verdict: "flag_for_rejection"`) when: company appears defunct, has been acquired and absorbed, is not actually AI-focused, is not headquartered in AU or NZ, or its identity is genuinely ambiguous from public sources. Do not auto-reject — this is a flag for a human reviewer.
6. **Flag for review** (`verdict: "flag_for_review"`) when you have material doubt that a human should resolve (e.g. the company moved cities to one not on the supported list, identity matches but website now points elsewhere, conflicting funding figures across sources). Include the issue in `notes`.
7. **Confidence** is your honest 0.0–1.0 score for the verification overall, not for any single field.
8. **Profile sources.** When you provide updates, populate `profile_sources` (in `updates`) with the same authoritative URLs you cited.

## Output schema

Return a single JSON array. One object per company in the order they appear above. Wrap the array in a fenced ` ```json ` block so it parses cleanly.

```json
[
  {
    "id": "<company uuid, copied verbatim from the input>",
    "name": "<company name, for human reference>",
    "verdict": "confirm" | "update" | "flag_for_review" | "flag_for_rejection",
    "updates": {
      "field_name": "new value (only fields that changed; omit unchanged)"
    },
    "evidence_urls": ["https://...", "https://..."],
    "confidence": 0.92,
    "notes": "One paragraph for the human reviewer. Mention anything surprising, conflicting, or worth a follow-up."
  }
]
```

## Worked example

Suppose the input contained this company:

```
- id: 00000000-0000-0000-0000-000000000abc
  name: ExampleAI
  country: AU
  city: Sydney
  website: https://example.ai
  sector_tags: [vertical_legal]
  stage: seed
  founded_year: 2021
  summary: Legal AI assistant for ANZ law firms.
  founders: [Jane Doe]
  total_raised_usd: 2000000
  headcount_estimate: 12
```

After verification you discover ExampleAI raised a Series A of AUD 18M in Oct 2025 (per AFR), now has ~35 staff (per LinkedIn), and the website is unchanged. The output entry is:

```json
{
  "id": "00000000-0000-0000-0000-000000000abc",
  "name": "ExampleAI",
  "verdict": "update",
  "updates": {
    "stage": "series_a",
    "total_raised_usd": 14000000,
    "total_raised_currency_raw": "AUD 20M cumulative",
    "total_raised_as_of": "2025-10-14",
    "total_raised_source_url": "https://www.afr.com/...",
    "headcount_estimate": 35,
    "headcount_as_of": "2026-04-01",
    "headcount_source_url": "https://www.linkedin.com/company/example-ai/",
    "profile_sources": [
      "https://www.afr.com/...",
      "https://www.linkedin.com/company/example-ai/"
    ]
  },
  "evidence_urls": [
    "https://www.afr.com/...",
    "https://www.linkedin.com/company/example-ai/"
  ],
  "confidence": 0.9,
  "notes": "Series A funding well documented. Headcount from LinkedIn band 26-50, took midpoint."
}
```

## Begin verification

Work through the {{COMPANY_COUNT}} companies above in order. Return one JSON array, no preamble, no trailing commentary outside the fenced JSON block.
