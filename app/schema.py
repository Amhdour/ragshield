"""Structured output schema and validation helpers for chat responses."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class Citation(BaseModel):
    """A source citation tied to a retrieved document."""

    doc_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class AnswerPayload(BaseModel):
    """Canonical structured answer returned by the API."""

    answer: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    confidence: Literal["low", "med", "high"]
    refusal_reason: str | None = None


def _extract_json_candidate(text: str) -> str:
    """Extract a likely JSON object from model output text."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.replace("json", "", 1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped


def _fallback_payload(reason: str) -> AnswerPayload:
    """Return a safe low-confidence fallback payload."""
    return AnswerPayload(
        answer="I don't know",
        citations=[],
        confidence="low",
        refusal_reason=reason,
    )


def validate_or_repair_output(raw_output: str, has_context: bool) -> AnswerPayload:
    """Validate model output as `AnswerPayload`, with fallback on invalid data."""
    if not has_context:
        return _fallback_payload("No relevant context retrieved")

    candidate = _extract_json_candidate(raw_output)

    # Optional Guardrails path; fallback to Pydantic-only validation if unavailable.
    try:
        from guardrails import Guard  # type: ignore

        guard = Guard.for_pydantic(output_class=AnswerPayload)
        guarded = guard.parse(candidate)
        validated_output = getattr(guarded, "validated_output", None)
        if isinstance(validated_output, dict):
            return AnswerPayload.model_validate(validated_output)
    except Exception:
        pass

    try:
        parsed = json.loads(candidate)
        return AnswerPayload.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return _fallback_payload("Output schema validation failed")
