"""FastAPI entrypoint exposing a minimal /chat endpoint."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.config import settings
from app.graph import build_chat_graph
from app.policy import check_policy
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


@app.on_event("startup")
def startup_log() -> None:
    """Log tracing backend mode once at startup."""
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY and settings.LANGFUSE_HOST:
        print("Langfuse enabled")
    else:
        print("Local tracing enabled")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Run RAG graph and return structured answer payload."""
    trace = start_trace(request_id=str(uuid4()), metadata={"query": request.query})
    request_span = start_span(trace, "request", {"endpoint": "/chat"})
    try:
        result = chat_graph.invoke({"query": request.query, "trace": trace})
        payload = AnswerPayload.model_validate(result.get("answer_payload", {}))

        policy_span = start_span(
            trace,
            "policy",
            {
                "confidence": payload.confidence,
                "citation_count": len(payload.citations),
            },
        )
        allow, reasons = check_policy(payload.model_dump())
        end_span(policy_span, {"allow": allow, "reasons": reasons}, "ok")

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
