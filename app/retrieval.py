"""Weaviate retrieval helper with bm25/hybrid mode selection."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import weaviate

from app.config import settings
from app.embeddings import embed_texts


def embeddings_available() -> bool:
    """Return True when embedding credentials are present for vector-capable retrieval."""
    return bool(settings.EMBEDDING_MODEL and settings.EMBEDDING_API_KEY)


def _to_int(value: Any) -> int | None:
    """Best-effort int coercion for metadata fields."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    """Best-effort float coercion for score-like fields."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_score(obj: Any) -> float | None:
    """Extract score from Weaviate object metadata when available."""
    metadata = getattr(obj, "metadata", None)
    if metadata is None:
        return None
    for attr in ("score", "certainty", "distance"):
        score = _to_float(getattr(metadata, attr, None))
        if score is not None:
            return score
    if isinstance(metadata, dict):
        for key in ("score", "certainty", "distance"):
            score = _to_float(metadata.get(key))
            if score is not None:
                return score
    return None


def _docs_from_response(response: Any) -> list[dict[str, str | int | float | None]]:
    """Normalize Weaviate response objects into app retrieval records."""
    docs: list[dict[str, str | int | float | None]] = []
    for obj in getattr(response, "objects", []) or []:
        props = obj.properties
        text = str(props.get("text", ""))
        docs.append(
            {
                "doc_id": str(props.get("doc_id", "")),
                "chunk_id": str(props.get("chunk_id", "")),
                "chunk_index": _to_int(props.get("chunk_index")),
                "start_char": _to_int(props.get("start_char")),
                "end_char": _to_int(props.get("end_char")),
                "category": str(props.get("category", "")),
                "source": str(props.get("source", "")),
                "score": _extract_score(obj),
                "text": text,
                "content": text,
            }
        )
    return docs


def _resolve_retrieval_mode() -> str:
    """Resolve runtime retrieval mode from configured value and capabilities."""
    mode = settings.RETRIEVAL_MODE
    if mode not in {"auto", "bm25", "hybrid"}:
        raise RuntimeError("Unsupported RETRIEVAL_MODE. Expected one of: auto, bm25, hybrid")
    if mode == "auto":
        return "hybrid" if embeddings_available() else "bm25"
    if mode == "hybrid" and not embeddings_available():
        return "bm25"
    return mode


def retrieve(query: str, top_k: int) -> list[dict[str, str | int | float | None]]:
    """Retrieve matching document chunks from RagDoc using configured retrieval mode."""
    endpoint = urlparse(settings.WEAVIATE_URL)
    if not endpoint.hostname:
        raise RuntimeError(f"Invalid WEAVIATE_URL: {settings.WEAVIATE_URL}")

    if top_k < 1:
        raise RuntimeError("top_k must be >= 1")

    mode = _resolve_retrieval_mode()

    try:
        with weaviate.connect_to_custom(
            http_host=endpoint.hostname,
            http_port=endpoint.port or 8080,
            http_secure=endpoint.scheme == "https",
            grpc_host=endpoint.hostname,
            grpc_port=50051,
            grpc_secure=False,
        ) as client:
            collection = client.collections.get("RagDoc")
            if mode == "hybrid":
                query_vector = embed_texts([query])[0]
                response = collection.query.hybrid(query=query, vector=query_vector, limit=top_k)
            else:
                response = collection.query.bm25(query=query, limit=top_k)
            return _docs_from_response(response)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Retrieval failed. Ensure Weaviate is running and RagDoc has been ingested."
        ) from exc
