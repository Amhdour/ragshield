"""Minimal LangGraph RAG flow for chat responses."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.llm import generate
from app.prompts import SYSTEM_PROMPT, USER_TEMPLATE
from app.retrieval import retrieve
from app.schema import validate_or_repair_output
from app.tracing import TraceHandle, end_span, start_span


class ChatState(TypedDict, total=False):
    """State carried across the RAG pipeline."""

    query: str
    trace: TraceHandle
    context_docs: list[dict[str, str]]
    draft_answer: str
    answer_payload: dict[str, object]


def retrieve_node(state: ChatState) -> ChatState:
    """Fetch relevant context documents for the input query."""
    trace = state["trace"]
    span = start_span(trace, "retrieval", {"top_k": settings.TOP_K})
    docs = retrieve(state["query"], top_k=settings.TOP_K)
    end_span(
        span,
        {
            "doc_ids": [doc.get("doc_id", "") for doc in docs],
            "doc_count": len(docs),
        },
        "ok",
    )
    return {"context_docs": docs}


def draft_node(state: ChatState) -> ChatState:
    """Draft an answer from retrieved context using the LLM wrapper."""
    trace = state["trace"]
    context_lines = [
        f"doc_id={doc.get('doc_id', '')}; category={doc.get('category', '')}; source={doc.get('source', '')}; content={doc.get('content', '')}"
        for doc in state.get("context_docs", [])
    ]
    stuffed_context = "\n".join(context_lines) if context_lines else "(no context)"
    user_prompt = USER_TEMPLATE.format(query=state["query"], context=stuffed_context)
    user_prompt += (
        "\nReturn ONLY valid JSON with keys: answer, citations, confidence, refusal_reason. "
        "Each citation must contain doc_id and quote."
    )

    span = start_span(trace, "llm", {"model": settings.LITELLM_MODEL})
    answer = generate(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )
    end_span(
        span,
        {
            "model": settings.LITELLM_MODEL,
            "token_usage": "unavailable",
            "answer_chars": len(answer),
        },
        "ok",
    )
    return {"draft_answer": answer}


def finalize_node(state: ChatState) -> ChatState:
    """Validate/repair draft into structured `AnswerPayload` JSON."""
    trace = state["trace"]
    span = start_span(trace, "validation", {})
    payload = validate_or_repair_output(
        raw_output=state.get("draft_answer", ""),
        context_docs=state.get("context_docs", []),
    )
    payload_json = json.loads(payload.model_dump_json())
    end_span(
        span,
        {
            "confidence": payload_json.get("confidence"),
            "citation_count": len(payload_json.get("citations", [])),
            "refusal_reason": payload_json.get("refusal_reason"),
        },
        "ok",
    )
    return {"answer_payload": payload_json}


def build_chat_graph() -> Any:
    """Build and compile the chat graph."""
    graph = StateGraph(ChatState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("draft", draft_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
