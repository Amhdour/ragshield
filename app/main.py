"""FastAPI entrypoint exposing a minimal /chat endpoint."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
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
    """Log tracing mode once at startup."""
    if settings.LANGFUSE_HOST and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        print("Langfuse credentials detected; using local tracing sink.")


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
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        trace.flush()
