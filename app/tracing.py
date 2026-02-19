"""Local tracing utilities (no external Langfuse dependency)."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator
from uuid import uuid4


@dataclass(slots=True)
class TraceHandle:
    """Trace handle abstraction used by request and graph code."""

    enabled: bool
    trace_id: str
    name: str
    input: dict[str, object]
    _events: list[dict[str, object]] = field(default_factory=list)

    @contextmanager
    def span(self, name: str, input: dict[str, object]) -> Iterator[None]:
        """Open a tracing span around a unit of work."""
        if self.enabled:
            self._events.append({"type": "span_start", "name": name, "input": input})
        try:
            yield
        finally:
            if self.enabled:
                self._events.append({"type": "span_end", "name": name})

    def add_output(self, output: dict[str, object]) -> None:
        """Add final output attributes to the trace."""
        if self.enabled:
            self._events.append({"type": "output", "output": output})

    def flush(self) -> None:
        """Flush trace events to stdout."""
        if not self.enabled:
            return
        print(f"[trace] {self.trace_id} {self.name}: {len(self._events)} events")


def start_trace(name: str, input: dict[str, object]) -> TraceHandle:
    """Start a local trace for request execution."""
    return TraceHandle(enabled=True, trace_id=str(uuid4()), name=name, input=input)
