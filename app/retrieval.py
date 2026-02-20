"""Simple Weaviate retrieval helper returning typed dictionaries."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import weaviate

from app.config import settings


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


def retrieve(query: str, top_k: int) -> list[dict[str, str | int | None]]:
    """Retrieve matching document chunks from RagDoc by BM25 query.

    Retrieval strategy selection is prepared for RETRIEVAL_MODE (`auto|bm25|hybrid`),
    but currently executes BM25 only.
    """
    endpoint = urlparse(settings.WEAVIATE_URL)
    if not endpoint.hostname:
        raise RuntimeError(f"Invalid WEAVIATE_URL: {settings.WEAVIATE_URL}")

    if top_k < 1:
        raise RuntimeError("top_k must be >= 1")

    if settings.RETRIEVAL_MODE not in {"auto", "bm25", "hybrid"}:
        raise RuntimeError("Unsupported RETRIEVAL_MODE. Expected one of: auto, bm25, hybrid")

    if settings.RETRIEVAL_MODE == "hybrid" and not embeddings_available():
        # Preparation path: hybrid mode will require embeddings when implemented.
        pass

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
            response = collection.query.bm25(query=query, limit=top_k)
            docs: list[dict[str, str | int | None]] = []
            for obj in response.objects:
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
                        "text": text,
                        "content": text,
                    }
                )
            return docs
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Retrieval failed. Ensure Weaviate is running and RagDoc has been ingested."
        ) from exc
