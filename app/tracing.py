"""Tracing adapter with Langfuse support and safe local fallback."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Iterator
from uuid import uuid4

from app.config import settings


_TRACE_CAPTURE_LIMIT = 160


def _safe_value(value: object) -> object:
    """Redact or truncate sensitive text unless DEBUG_TRACE is enabled."""
    if settings.DEBUG_TRACE:
        return value
    if isinstance(value, str):
        text = value.strip()
        if len(text) > _TRACE_CAPTURE_LIMIT:
            text = text[:_TRACE_CAPTURE_LIMIT] + "..."
        return {"sha256": sha256(text.encode("utf-8")).hexdigest(), "preview": text}
    if isinstance(value, dict):
        return {k: _safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_value(v) for v in value]
    return value


@dataclass(slots=True)
class TraceSpan:
    """A thin span wrapper with a unified end() method."""

    _impl: Any
    _events: list[dict[str, object]]
    _name: str

    def end(self, output: dict[str, object] | None = None, status: str = "ok") -> None:
        """Close the span and attach output when available."""
        safe_output = _safe_value(output or {})
        if self._impl is None:
            self._events.append(
                {
                    "type": "span_end",
                    "name": self._name,
                    "status": status,
                    "output": safe_output,
                }
            )
            return
        try:
            self._impl.end(output=safe_output, status_message=status)
        except TypeError:
            self._impl.end(output=safe_output)
        except Exception:
            # Trace failures should never break app flow.
            pass


@dataclass(slots=True)
class TraceHandle:
    """Trace handle abstraction used by request and graph code."""

    enabled: bool
    trace_id: str
    name: str
    input: dict[str, object]
    backend: str
    _trace_impl: Any = None
    _events: list[dict[str, object]] = field(default_factory=list)

    def start_span(self, name: str, input: dict[str, object]) -> TraceSpan:
        """Create a span using Langfuse when available, else local events."""
        safe_input = _safe_value(input)
        if self._trace_impl is not None:
            try:
                impl = self._trace_impl.span(name=name, input=safe_input)
                return TraceSpan(_impl=impl, _events=self._events, _name=name)
            except Exception:
                pass
        self._events.append({"type": "span_start", "name": name, "input": safe_input})
        return TraceSpan(_impl=None, _events=self._events, _name=name)

    def end_trace(self, output: dict[str, object] | None = None, status: str = "ok") -> None:
        """End trace and attach output attributes."""
        safe_output = _safe_value(output or {})
        if self._trace_impl is not None:
            try:
                self._trace_impl.update(output=safe_output, metadata={"status": status})
                return
            except Exception:
                pass
        self._events.append({"type": "trace_end", "status": status, "output": safe_output})

    @contextmanager
    def span(self, name: str, input: dict[str, object]) -> Iterator[None]:
        """Backward-compatible context manager for spans."""
        span = self.start_span(name, input)
        try:
            yield
            span.end(status="ok")
        except Exception:
            span.end(status="error")
            raise

    def add_output(self, output: dict[str, object]) -> None:
        """Backward-compatible trace output helper."""
        self.end_trace(output=output, status="ok")

    def flush(self) -> None:
        """Flush trace output to backend or stdout."""
        if self.backend == "langfuse":
            try:
                if self._trace_impl is not None and hasattr(self._trace_impl, "client"):
                    self._trace_impl.client.flush()
            except Exception:
                pass
            return
        if self.enabled:
            print(f"[trace] {self.trace_id} {self.name}: {len(self._events)} events")


class _LegacySpanProxy:
    """Compatibility shim exposing end_span for existing call patterns."""

    def __init__(self, span: TraceSpan) -> None:
        self._span = span

    def end_span(self, output: dict[str, object] | None = None, status: str = "ok") -> None:
        """Proxy to TraceSpan.end."""
        self._span.end(output=output, status=status)


def _langfuse_ready() -> bool:
    """Return True when Langfuse credentials are configured."""
    return bool(
        settings.LANGFUSE_PUBLIC_KEY
        and settings.LANGFUSE_SECRET_KEY
        and settings.LANGFUSE_HOST
    )


def start_trace(request_id: str, metadata: dict[str, object]) -> TraceHandle:
    """Start a trace using Langfuse when configured, else local tracing."""
    trace_id = request_id or str(uuid4())
    if _langfuse_ready():
        try:
            from langfuse import Langfuse

            client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
            )
            trace_impl = client.trace(
                id=trace_id,
                name="ragshield_chat",
                input=_safe_value(metadata),
                metadata={"env": settings.RAGSHIELD_ENV},
            )
            return TraceHandle(
                enabled=True,
                trace_id=trace_id,
                name="ragshield_chat",
                input=metadata,
                backend="langfuse",
                _trace_impl=trace_impl,
            )
        except Exception:
            pass

    return TraceHandle(
        enabled=True,
        trace_id=trace_id,
        name="ragshield_chat",
        input=metadata,
        backend="local",
    )


def start_span(trace: TraceHandle, name: str, input: dict[str, object]) -> _LegacySpanProxy:
    """Start a span and return a handle that supports end_span()."""
    return _LegacySpanProxy(trace.start_span(name=name, input=input))


def end_span(span: _LegacySpanProxy, output: dict[str, object], status: str) -> None:
    """End a started span with output and status."""
    span.end_span(output=output, status=status)


def end_trace(trace: TraceHandle, output: dict[str, object], status: str) -> None:
    """End a trace with output and status."""
    trace.end_trace(output=output, status=status)
