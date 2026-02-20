"""Embedding helpers backed by LiteLLM-compatible embedding providers."""

from __future__ import annotations

from typing import Any

from app.config import settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed input texts using configured embedding provider and return vectors in input order."""
    if not texts:
        return []

    if not settings.embeddings_enabled:
        raise RuntimeError(
            "Embedding failed: embeddings are disabled because EMBEDDING_BASE_URL/EMBEDDING_MODEL are unset."
        )

    cleaned = [t.strip() for t in texts]
    if any(not t for t in cleaned):
        raise RuntimeError("Embedding failed: input texts must be non-empty strings.")

    try:
        from litellm import embedding
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Embedding failed: litellm package is not installed. Install project dependencies first."
        ) from exc

    request_kwargs: dict[str, Any] = {
        "model": settings.EMBEDDING_MODEL,
        "input": cleaned,
        "api_base": settings.EMBEDDING_BASE_URL,
    }
    if settings.EMBEDDING_API_KEY:
        request_kwargs["api_key"] = settings.EMBEDDING_API_KEY

    try:
        response = embedding(**request_kwargs)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Embedding failed for model {settings.EMBEDDING_MODEL} at {settings.EMBEDDING_BASE_URL}: {exc}"
        ) from exc

    data = getattr(response, "data", None)
    if not isinstance(data, list) or len(data) != len(cleaned):
        raise RuntimeError("Embedding failed: provider returned unexpected embedding payload size.")

    vectors: list[list[float]] = []
    for item in data:
        vector = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(vector, list) or not vector:
            raise RuntimeError("Embedding failed: provider returned invalid vector payload.")
        vectors.append([float(v) for v in vector])

    return vectors
