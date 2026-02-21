"""Embedding helpers backed by LiteLLM-compatible embedding providers."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)
_OPENROUTER_MODEL_IDS_CACHE: set[str] | None = None


def _fetch_openrouter_embedding_model_ids(api_key: str) -> set[str]:
    """Fetch and cache OpenRouter embedding model IDs for this process."""
    global _OPENROUTER_MODEL_IDS_CACHE

    if _OPENROUTER_MODEL_IDS_CACHE is not None:
        return _OPENROUTER_MODEL_IDS_CACHE

    try:
        import requests
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Failed to validate OpenRouter EMBEDDING_MODEL: requests dependency is unavailable."
        ) from exc

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/embeddings/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Failed to validate OpenRouter EMBEDDING_MODEL via model discovery endpoint. "
            "Run scripts/check_openrouter_embeddings_models.py to inspect available model IDs. "
            f"Details: {exc}"
        ) from exc

    model_ids: set[str] = set()
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    model_id = item.get("id")
                    if isinstance(model_id, str) and model_id.strip():
                        model_ids.add(model_id.strip())

    _OPENROUTER_MODEL_IDS_CACHE = model_ids
    return model_ids


def validate_embedding_model_id(model_id: str) -> None:
    """Validate embedding model id with provider-aware checks."""
    normalized_model_id = (model_id or "").strip()
    if not normalized_model_id:
        raise RuntimeError("Invalid EMBEDDING_MODEL: value must be non-empty.")

    base_url = (settings.EMBEDDING_BASE_URL or "").lower()
    if "openrouter.ai" not in base_url:
        return

    api_key = (settings.EMBEDDING_API_KEY or "").strip()
    if not api_key:
        logger.warning(
            "OpenRouter embedding model availability check skipped: EMBEDDING_API_KEY is not set. "
            "Cannot verify EMBEDDING_MODEL '%s' against OpenRouter catalog.",
            normalized_model_id,
        )
        return

    available_ids = _fetch_openrouter_embedding_model_ids(api_key)
    if normalized_model_id not in available_ids:
        raise RuntimeError(
            f"EMBEDDING_MODEL '{normalized_model_id}' not available on OpenRouter. "
            "Run scripts/check_openrouter_embeddings_models.py to choose a valid one."
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
