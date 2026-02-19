"""Typed service interfaces for the ragshield runtime."""

from __future__ import annotations

from typing import Protocol


class Retriever(Protocol):
    """Retrieves grounded context passages for a query."""

    def retrieve(self, query: str, top_k: int = 4) -> list[str]:
        """Return top-k matching passages for the supplied query."""


class LLMRouter(Protocol):
    """Routes a prompt to a configured model provider."""

    def generate(self, prompt: str) -> str:
        """Generate a text response for a prompt."""


class PolicyGate(Protocol):
    """Evaluates policy decisions against OPA."""

    def allow(self, query: str, context: list[str], response: str) -> bool:
        """Return True when policy allows returning the response."""
