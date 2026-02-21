"""FastAPI entrypoint exposing a minimal /chat endpoint."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Header
from pydantic import BaseModel, Field

from app.config import settings
from app.embeddings import validate_embedding_model_id
from app.graph import build_chat_graph
from app.policy import check_policy, check_pre_action_policy
from app.retrieval import embeddings_available
from app.schema import AnswerPayload
from app.tracing import end_span, end_trace, start_span, start_trace


class ChatRequest(BaseModel):
    """Incoming chat request payload."""

    query: str = Field(min_length=1)


class ChatResponse(AnswerPayload):
    """Outgoing chat response payload with optional trace id."""

    trace_id: str | None = None


app = FastAPI(title="ragshield")
chat_graph = build_chat_graph()


def _normalize_role(value: str | None) -> str:
    """Normalize untrusted role header to policy-supported roles."""
    if value and value.lower() == "admin":
        return "admin"
    return "user"


@app.on_event("startup")
def startup_log() -> None:
    """Log tracing backend mode once at startup and validate hybrid embedding config."""
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY and settings.LANGFUSE_HOST:
        print("Langfuse enabled")
    else:
        print("Local tracing enabled")

    should_use_hybrid = settings.RETRIEVAL_MODE == "hybrid" or (
        settings.RETRIEVAL_MODE == "auto" and embeddings_available()
    )
    if should_use_hybrid and settings.EMBEDDING_MODEL:
        validate_embedding_model_id(settings.EMBEDDING_MODEL)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, x_role: str | None = Header(default=None, alias="X-Role")) -> ChatResponse:
    """Run RAG graph and return structured answer payload."""
    user_role = _normalize_role(x_role)
    trace = start_trace(
        request_id=str(uuid4()),
        metadata={"query": request.query, "user_role": user_role},
    )
    request_span = start_span(trace, "request", {"endpoint": "/chat", "user_role": user_role})
    try:
        result = chat_graph.invoke({"query": request.query, "trace": trace, "user_role": user_role})
        payload = AnswerPayload.model_validate(result.get("answer_payload", {}))

        policy_span = start_span(
            trace,
            "policy",
            {
                "confidence": payload.confidence,
                "citation_count": len(payload.citations),
            },
        )
        context_docs = result.get("context_docs", [])
        risk_flags = result.get("risk_flags", {})

        return_allowed, return_reasons = check_pre_action_policy(
            action="return_answer",
            requested_data_scope="knowledge_base",
            user_role="admin" if user_role == "admin" else "user",
            injection_suspected=bool(risk_flags.get("injection_suspected", False)),
            exfil_suspected=bool(risk_flags.get("exfil_suspected", False)),
            response_is_refusal=bool(payload.refusal_reason),
        )
        if not return_allowed:
            payload.answer = "I can’t comply with that request."
            payload.citations = []
            payload.confidence = "low"
            payload.refusal_reason = "; ".join(return_reasons) if return_reasons else "Policy denied"

        context_chunks = [
            {
                "doc_id": str(doc.get("doc_id", "")),
                "chunk_id": str(doc.get("chunk_id", "")),
                "chunk_index": str(doc.get("chunk_index", "")),
                "start_char": str(doc.get("start_char", "")),
                "end_char": str(doc.get("end_char", "")),
                "text": str(doc.get("text", doc.get("content", ""))),
            }
            for doc in context_docs
        ]
        policy_input = payload.model_dump()
        policy_input["context_chunks"] = context_chunks
        allow, reasons = check_policy(policy_input)
        end_span(
            policy_span,
            {
                "allow": allow,
                "reasons": reasons,
                "return_allow": return_allowed,
                "return_reasons": return_reasons,
            },
            "ok",
        )

        if not allow:
            payload.answer = "I can’t comply with that request."
            payload.citations = []
            payload.confidence = "low"
            payload.refusal_reason = "; ".join(reasons) if reasons else "Policy denied"

        final_payload = payload.model_dump()
        end_span(
            request_span,
            {
                "trace_id": trace.trace_id,
                "confidence": final_payload.get("confidence"),
                "citation_count": len(final_payload.get("citations", [])),
            },
            "ok",
        )
        end_trace(trace, final_payload, "ok")
        response = ChatResponse(**final_payload, trace_id=trace.trace_id)
        return response
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "Retrieval failed" in message or "Weaviate" in message:
            refusal_reason = "Retrieval failed: Weaviate unavailable"
        else:
            refusal_reason = "Policy engine unavailable"
        payload = AnswerPayload(
            answer="I can’t comply with that request.",
            citations=[],
            confidence="low",
            refusal_reason=refusal_reason,
        )
        error_payload = payload.model_dump()
        end_span(request_span, {"error": refusal_reason}, "error")
        end_trace(trace, error_payload, "error")
        return ChatResponse(**error_payload, trace_id=trace.trace_id)
    finally:
        trace.flush()
