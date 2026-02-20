"""Structured output schema and validation helpers for chat responses."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


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


def _short_quote(content: str, limit: int = 160) -> str:
    """Create a short citation quote from a document content field."""
    snippet = " ".join(content.split())
    return snippet[:limit] if snippet else "Context excerpt unavailable"


def _context_map(context_docs: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Index context documents by doc_id."""
    return {
        str(doc.get("doc_id", "")).strip(): doc
        for doc in context_docs
        if str(doc.get("doc_id", "")).strip()
    }


def _normalize_payload(payload: AnswerPayload, context_docs: list[dict[str, str]]) -> AnswerPayload:
    """Ensure citations align to retrieved docs and confidence/citation invariants hold."""
    docs_by_id = _context_map(context_docs)

    valid_citations: list[Citation] = []
    for citation in payload.citations:
        if citation.doc_id not in docs_by_id:
            continue
        quote = citation.quote.strip() or _short_quote(docs_by_id[citation.doc_id].get("content", ""))
        valid_citations.append(Citation(doc_id=citation.doc_id, quote=quote))

    if payload.confidence in {"med", "high"} and not valid_citations:
        first_doc_id = next(iter(docs_by_id.keys()), "")
        if first_doc_id:
            valid_citations = [
                Citation(
                    doc_id=first_doc_id,
                    quote=_short_quote(docs_by_id[first_doc_id].get("content", "")),
                )
            ]
        else:
            return _fallback_payload("No valid citations for med/high confidence")

    return AnswerPayload(
        answer=payload.answer,
        citations=valid_citations,
        confidence=payload.confidence,
        refusal_reason=payload.refusal_reason,
    )


def _parse_and_validate(candidate: str, context_docs: list[dict[str, str]]) -> AnswerPayload:
    """Parse JSON candidate and validate it against `AnswerPayload`."""
    parsed: Any = json.loads(candidate)
    payload = AnswerPayload.model_validate(parsed)
    return _normalize_payload(payload, context_docs)


def _repair_once(raw_output: str, context_docs: list[dict[str, str]]) -> str:
    """Attempt one model-assisted repair to strict JSON output."""
    from app.llm import generate
    from app.prompts import REPAIR_PROMPT

    context_lines = [
        f"doc_id={doc.get('doc_id', '')}; content={doc.get('content', '')}"
        for doc in context_docs
    ]
    repair_messages = [
        {"role": "system", "content": REPAIR_PROMPT},
        {
            "role": "user",
            "content": (
                "Fix this output to valid JSON matching schema only.\n"
                f"Previous output:\n{raw_output}\n\n"
                f"Available evidence:\n{chr(10).join(context_lines)}"
            ),
        },
    ]
    return generate(messages=repair_messages)


def validate_or_repair_output(raw_output: str, context_docs: list[dict[str, str]]) -> AnswerPayload:
    """Validate JSON output; attempt one repair; fallback safely on failure."""
    if not context_docs:
        return _fallback_payload("No relevant context retrieved")

    candidate = _extract_json_candidate(raw_output)

    # Parse/validate first.
    try:
        return _parse_and_validate(candidate, context_docs)
    except (json.JSONDecodeError, ValidationError, TypeError):
        pass

    # Optional Guardrails path, if available.
    try:
        from guardrails import Guard  # type: ignore

        guard = Guard.for_pydantic(output_class=AnswerPayload)
        guarded = guard.parse(candidate)
        validated_output = getattr(guarded, "validated_output", None)
        if isinstance(validated_output, dict):
            payload = AnswerPayload.model_validate(validated_output)
            return _normalize_payload(payload, context_docs)
    except Exception:
        pass

    # One repair attempt with the model.
    try:
        repaired_raw = _repair_once(raw_output=raw_output, context_docs=context_docs)
        repaired_candidate = _extract_json_candidate(repaired_raw)
        return _parse_and_validate(repaired_candidate, context_docs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Schema repair failed; returning safe refusal payload (%s)", exc)
        return _fallback_payload("Output schema validation failed")
