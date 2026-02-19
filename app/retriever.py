"""Backward-compatible retrieval shim.

Use app.retrieval.retrieve as the canonical retrieval module.
"""

from __future__ import annotations

from app.retrieval import retrieve

__all__ = ["retrieve"]
