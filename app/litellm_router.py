"""Backward-compatible LLM shim.

Use app.llm.generate as the canonical LLM module.
"""

from __future__ import annotations

from app.llm import generate

__all__ = ["generate"]
