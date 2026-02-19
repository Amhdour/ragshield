"""Prompt templates for the minimal RAG pipeline."""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You are a retrieval-grounded assistant. "
    "Answer only from the retrieved context. "
    "Include citations using [doc_id] notation. "
    "If the answer is not in context, say exactly: I don't know."
)

USER_TEMPLATE = """Question:
{query}

Retrieved context:
{context}

Return a concise answer with citations like [doc-123].
"""
