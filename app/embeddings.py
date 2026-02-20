"""Embedding helpers backed by LiteLLM-compatible embedding providers."""

from __future__ import annotations

from typing import Any

from app.config import settings


def validate_embedding_model_id(model_id: str) -> None:
    """Validate embedding model id conventions for known providers."""
    base_url = (settings.EMBEDDING_BASE_URL or "").lower()
    if "openrouter.ai" in base_url and "/" not in model_id:
        raise RuntimeError(
            "Invalid EMBEDDING_MODEL for OpenRouter. OpenRouter model IDs are typically "
            "namespaced like provider/model. Run scripts/check_openrouter_embeddings_models.py "
            "to pick a valid id."
        )


def _extract_vector(item: Any) -> list[float] | None:
    """Extract embedding vector from dict/object payloads robustly."""
    if isinstance(item, dict):
        raw = item.get("embedding")
    else:
        raw = getattr(item, "embedding", None)
    if not isinstance(raw, list) or not raw:
        return None
    try:
        return [float(value) for value in raw]
    except (TypeError, ValueError):
        return None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed input texts using configured embedding provider and return vectors in input order."""
    if not texts:
        return []

    if not settings.embeddings_enabled:
        raise RuntimeError(
            "Embedding failed: EMBEDDING_BASE_URL and EMBEDDING_MODEL must both be set. "
            "Configure EMBEDDING_* vars (for example OpenRouter) or run ingest with --no-embeddings for BM25-only mode."
        )

    validate_embedding_model_id(str(settings.EMBEDDING_MODEL))

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
        vector = _extract_vector(item)
        if vector is None:
            raise RuntimeError("Embedding failed: provider returned invalid vector payload.")
        vectors.append(vector)

    return vectors
