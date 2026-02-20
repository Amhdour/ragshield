"""Structured output schema and validation helpers for chat responses."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class Citation(BaseModel):
    """A source citation tied to a retrieved document chunk."""

    doc_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    chunk_index: int | None = None
    start_char: int | None = None
    end_char: int | None = None
    quote: str = Field(min_length=1)
    score: float | None = None


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


def _chunk_map(
    context_docs: list[dict[str, str | int | None]],
) -> dict[tuple[str, str], dict[str, str | int | None]]:
    """Index context chunks by (doc_id, chunk_id)."""
    indexed: dict[tuple[str, str], dict[str, str | int | None]] = {}
    for doc in context_docs:
        doc_id = str(doc.get("doc_id", "")).strip()
        chunk_id = str(doc.get("chunk_id", "")).strip()
        if doc_id and chunk_id:
            indexed[(doc_id, chunk_id)] = doc
    return indexed


def _coerce_int(value: Any) -> int | None:
    """Best-effort int parsing from citation/context metadata values."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _metadata_matches(citation: Citation, chunk: dict[str, str | int | None]) -> bool:
    """Validate optional citation metadata against chunk metadata when present."""
    expected_chunk_index = _coerce_int(chunk.get("chunk_index"))
    if citation.chunk_index is not None and citation.chunk_index != expected_chunk_index:
        return False

    expected_start = _coerce_int(chunk.get("start_char"))
    if citation.start_char is not None and citation.start_char != expected_start:
        return False

    expected_end = _coerce_int(chunk.get("end_char"))
    if citation.end_char is not None and citation.end_char != expected_end:
        return False

    return True


def _degrade_confidence(confidence: Literal["low", "med", "high"]) -> Literal["low", "med", "high"]:
    """Step confidence down by one tier."""
    if confidence == "high":
        return "med"
    if confidence == "med":
        return "low"
    return "low"


def _normalize_payload(
    payload: AnswerPayload,
    context_docs: list[dict[str, str | int | None]],
) -> AnswerPayload:
    """Keep only auditable citations and adjust confidence when citations are invalid."""
    chunks = _chunk_map(context_docs)

    valid_citations: list[Citation] = []
    invalid_count = 0
    for citation in payload.citations:
        key = (citation.doc_id, citation.chunk_id)
        chunk = chunks.get(key)
        if chunk is None:
            invalid_count += 1
            continue

        if not _metadata_matches(citation, chunk):
            invalid_count += 1
            continue

        chunk_text = str(chunk.get("text", chunk.get("content", "")))
        candidate_quote = citation.quote.strip()
        if not candidate_quote or candidate_quote not in chunk_text:
            invalid_count += 1
            continue

        score = citation.score
        if score is not None:
            try:
                score = max(0.0, min(1.0, float(score)))
            except Exception:
                score = None

        valid_citations.append(
            Citation(
                doc_id=citation.doc_id,
                chunk_id=citation.chunk_id,
                chunk_index=_coerce_int(chunk.get("chunk_index")),
                start_char=_coerce_int(chunk.get("start_char")),
                end_char=_coerce_int(chunk.get("end_char")),
                quote=candidate_quote,
                score=score,
            )
        )

    normalized_confidence = payload.confidence
    if invalid_count > 0:
        normalized_confidence = _degrade_confidence(normalized_confidence)
    if normalized_confidence in {"med", "high"} and not valid_citations:
        normalized_confidence = "low"

    refusal_reason = payload.refusal_reason
    if invalid_count > 0 and normalized_confidence == "low" and not refusal_reason:
        refusal_reason = "Dropped invalid citations during validation"

    return AnswerPayload(
        answer=payload.answer,
        citations=valid_citations,
        confidence=normalized_confidence,
        refusal_reason=refusal_reason,
    )


def _parse_and_validate(
    candidate: str,
    context_docs: list[dict[str, str | int | None]],
) -> AnswerPayload:
    """Parse JSON candidate and validate it against `AnswerPayload`."""
    parsed: Any = json.loads(candidate)
    payload = AnswerPayload.model_validate(parsed)
    return _normalize_payload(payload, context_docs)


def _repair_once(raw_output: str, context_docs: list[dict[str, str | int | None]]) -> str:
    """Attempt one model-assisted repair to strict JSON output."""
    from app.llm import generate
    from app.prompts import REPAIR_PROMPT

    context_lines = [
        (
            f"doc_id={doc.get('doc_id', '')}; "
            f"chunk_id={doc.get('chunk_id', '')}; "
            f"chunk_index={doc.get('chunk_index', '')}; "
            f"start_char={doc.get('start_char', '')}; "
            f"end_char={doc.get('end_char', '')}; "
            f"text={doc.get('text', doc.get('content', ''))}"
        )
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


def validate_or_repair_output(
    raw_output: str,
    context_docs: list[dict[str, str | int | None]],
) -> AnswerPayload:
    """Validate JSON output; attempt one repair; fallback safely on failure."""
    if not context_docs:
        return _fallback_payload("No relevant context retrieved")

    candidate = _extract_json_candidate(raw_output)

    try:
        return _parse_and_validate(candidate, context_docs)
    except (json.JSONDecodeError, ValidationError, TypeError):
        pass

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

    try:
        repaired_raw = _repair_once(raw_output=raw_output, context_docs=context_docs)
        repaired_candidate = _extract_json_candidate(repaired_raw)
        return _parse_and_validate(repaired_candidate, context_docs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Schema repair failed; returning safe refusal payload (%s)", exc)
        return _fallback_payload("Output schema validation failed")
