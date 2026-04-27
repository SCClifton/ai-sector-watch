"""Validate auto-discovered company candidates with the LLM client."""

from __future__ import annotations

from ai_sector_watch.extraction.claude_client import ClaudeClient
from ai_sector_watch.extraction.prompts import (
    VALIDATE_COMPANY_SYSTEM,
    VALIDATE_COMPANY_USER_TEMPLATE,
)
from ai_sector_watch.extraction.schema import CompanyValidation


def validate_company(
    client: ClaudeClient,
    *,
    name: str,
    context: str,
    max_tokens: int = 256,
) -> CompanyValidation:
    """Ask the model whether `name` is a real, current AI company.

    Pure orchestration: every side-effect (cache, budget, network) lives in
    `ClaudeClient`. The orchestrator decides what to do with the result.
    """
    prompt = VALIDATE_COMPANY_USER_TEMPLATE.format(name=name, context=context)
    response = client.structured_call(
        system=VALIDATE_COMPANY_SYSTEM,
        prompt=prompt,
        schema_cls=CompanyValidation,
        max_tokens=max_tokens,
    )
    return response.parsed  # type: ignore[return-value]


def is_acceptable(validation: CompanyValidation) -> bool:
    """Single source of truth for the gating rule."""
    return validation.is_valid and validation.is_ai_company
