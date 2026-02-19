"""Schema enforcement layer using Pydantic-compatible guardrails."""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError


class AnswerPayload(BaseModel):
    """Canonical output schema for RAG responses."""

    answer: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)


def enforce_schema(answer: str, citations: list[str]) -> AnswerPayload:
    """Validate and return the typed response payload."""
    try:
        return AnswerPayload(answer=answer, citations=citations)
    except ValidationError as exc:
        raise RuntimeError("Guardrails schema validation failed.") from exc
