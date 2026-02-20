"""Prompt templates for the minimal RAG pipeline."""

from __future__ import annotations

SYSTEM_PROMPT = """
You are a retrieval-grounded assistant.

Return only JSON. No markdown. No prose outside JSON.

Schema requirements:
- answer: string
- citations: array of objects, each object has:
  - doc_id: string (must match an evidence doc_id)
  - quote: string (short verbatim quote from evidence)
- confidence: one of "low", "med", "high"
- refusal_reason: string or null

Behavior rules:
- Use only retrieved evidence.
- If evidence is insufficient, return:
  - answer: "I don't know"
  - citations: []
  - confidence: "low"
  - refusal_reason: non-empty reason string
""".strip()

USER_TEMPLATE = """Question:
{query}

Retrieved evidence (stable IDs):
{context}

Return only JSON. No markdown. No prose outside JSON.
"""

REPAIR_PROMPT = """
Your previous output did not match the required JSON schema.

Return only valid JSON matching exactly:
{
  "answer": string,
  "citations": [{"doc_id": string, "quote": string}],
  "confidence": "low" | "med" | "high",
  "refusal_reason": string | null
}

No markdown. No explanations.
""".strip()
