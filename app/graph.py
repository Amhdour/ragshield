"""Minimal LangGraph RAG flow for chat responses."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.llm import generate
from app.policy import check_pre_action_policy
from app.prompts import SYSTEM_PROMPT, USER_TEMPLATE
from app.retrieval import retrieve
from app.schema import validate_or_repair_output
from app.tracing import TraceHandle, end_span, start_span


class ChatState(TypedDict, total=False):
    """State carried across the RAG pipeline."""

    query: str
    trace: TraceHandle
    context_docs: list[dict[str, object]]
    draft_answer: str
    answer_payload: dict[str, object]
    pre_action_denied: list[str]


def _deny_state(reasons: list[str]) -> ChatState:
    """Return state patch used when pre-action policy denies a tool call."""
    return {"pre_action_denied": reasons, "context_docs": [], "draft_answer": ""}


def retrieve_node(state: ChatState) -> ChatState:
    """Fetch relevant context documents for the input query."""
    trace = state["trace"]
    gate_span = start_span(trace, "pre_action_retrieval", {"action": "retrieval"})
    allowed, reasons = check_pre_action_policy(
        action="retrieval",
        query=state["query"],
        citation_count=0,
        requested_data_scope="knowledge_base",
    )
    end_span(gate_span, {"allow": allowed, "reasons": reasons}, "ok")
    if not allowed:
        return _deny_state(reasons)

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
    if state.get("pre_action_denied"):
        return {}

    trace = state["trace"]
    context_lines = [
        (
            f"evidence_id={doc.get('doc_id', '')}; "
            f"doc_id={doc.get('doc_id', '')}; "
            f"chunk_id={doc.get('chunk_id', '')}; "
            f"chunk_index={doc.get('chunk_index', '')}; "
            f"start_char={doc.get('start_char', '')}; "
            f"end_char={doc.get('end_char', '')}; "
            f"category={doc.get('category', '')}; "
            f"source={doc.get('source', '')}; "
            f"text={doc.get('text', doc.get('content', ''))}"
        )
        for doc in state.get("context_docs", [])
    ]
    stuffed_context = "\n".join(context_lines) if context_lines else "(no evidence)"
    user_prompt = USER_TEMPLATE.format(query=state["query"], context=stuffed_context)

    gate_span = start_span(trace, "pre_action_llm", {"action": "llm_generate"})
    allowed, reasons = check_pre_action_policy(
        action="llm_generate",
        query=state["query"],
        citation_count=len(state.get("context_docs", [])),
        requested_data_scope="generated_answer",
    )
    end_span(gate_span, {"allow": allowed, "reasons": reasons}, "ok")
    if not allowed:
        return {"pre_action_denied": reasons}

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

    if state.get("pre_action_denied"):
        reasons = state.get("pre_action_denied", [])
        payload_json = {
            "answer": "I can’t comply with that request.",
            "citations": [],
            "confidence": "low",
            "refusal_reason": "; ".join(reasons) if reasons else "Pre-action policy denied",
        }
        span = start_span(trace, "validation", {})
        end_span(span, {"pre_action_denied": reasons}, "ok")
        return {"answer_payload": payload_json}

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
