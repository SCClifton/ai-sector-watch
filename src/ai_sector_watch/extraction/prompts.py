"""Prompt strings for each Claude extraction step.

Kept terse to control token spend (PRD section 17 budget = $2 per run).
"""

from __future__ import annotations

EXTRACT_COMPANIES_SYSTEM = (
    "You extract company mentions from news items. "
    "Return only structured JSON matching the provided schema. "
    "Do not include commentary. Never use em dashes."
)

EXTRACT_COMPANIES_USER_TEMPLATE = """\
Extract every distinct company name mentioned in this news item.

For each company:
- Set `name` to the exact form used in the article.
- Set `confidence` between 0 and 1: how sure are you this is a real, current AI-native or AI-applied company.
- Set `is_anz` true only if the company is headquartered in Australia or New Zealand.
- Set `city` and `country` only if the article makes them obvious or you know them with high confidence.

Skip generic mentions (universities, governments, large incumbents like Google or OpenAI) unless they are the subject of an AI funding event.

Item title: {title}
Source: {source_slug} ({url})
Published: {published_at}

Body:
{body}
"""

VALIDATE_COMPANY_SYSTEM = (
    "You validate auto-discovered companies. "
    "Return only structured JSON matching the provided schema."
)

VALIDATE_COMPANY_USER_TEMPLATE = """\
Is `{name}` a real, currently operating AI-native or AI-applied company?

Context (from the news item that mentioned it):
{context}

If the name is ambiguous (multiple companies share it), set `is_valid` false.
If the company exists but is not in any AI/ML space, set `is_ai_company` false.
Set `canonical_name` only if the input is a misspelling or short form (e.g. "marqo.io" -> "Marqo").
"""

CLASSIFY_COMPANY_SYSTEM = (
    "You classify AI companies. Use only the provided sector tags and stage values."
)

CLASSIFY_COMPANY_USER_TEMPLATE = """\
Classify `{name}` for the ANZ AI ecosystem map.

Allowed sector tags (pick 1-4, primary first):
{sector_tags}

Allowed stages: pre_seed, seed, series_a, series_b_plus, mature.

Context:
{context}

Write a one-paragraph summary (no em dashes, active voice, under 80 words).
"""

EXTRACT_FUNDING_SYSTEM = (
    "You extract funding-event details from news items. "
    "Return only structured JSON matching the provided schema."
)

EXTRACT_FUNDING_USER_TEMPLATE = """\
Does this article describe a specific funding round for `{name}`?

If yes:
- Set `has_funding_event` true.
- Fill `announced_on`, `stage`, `amount_usd` (convert from any currency), `lead_investor`, and `investors` from the article.
- Use null for any field the article does not state.

Article:
{body}
"""

CLASSIFY_NEWS_SYSTEM = (
    "You classify news items. Return only structured JSON matching the schema."
)

CLASSIFY_NEWS_USER_TEMPLATE = """\
Classify this news item.

`kind` must be one of: funding, launch, hire, partnership, other.
`is_relevant` is true only if the item is relevant to the Australian or New Zealand AI ecosystem.

Title: {title}
Body: {body}
"""
