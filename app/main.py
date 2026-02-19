"""FastAPI entrypoint exposing a minimal /chat endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.graph import build_chat_graph
from app.policy import check_policy
from app.schema import AnswerPayload
from app.tracing import start_trace


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
    """Log local tracing mode once at startup."""
    print("Local tracing enabled")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Run RAG graph and return structured answer payload."""
    trace = start_trace(name="ragshield_chat", input={"query": request.query})
    try:
        result = chat_graph.invoke({"query": request.query, "trace": trace})
        payload = AnswerPayload.model_validate(result.get("answer_payload", {}))
        allow, reasons = check_policy(payload.model_dump())
        if not allow:
            payload.answer = "I can’t comply with that request."
            payload.citations = []
            payload.confidence = "low"
            payload.refusal_reason = "; ".join(reasons) if reasons else "Policy denied"
        response = ChatResponse(**payload.model_dump(), trace_id=trace.trace_id)
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
        return ChatResponse(**payload.model_dump(), trace_id=trace.trace_id)
    finally:
        trace.flush()
