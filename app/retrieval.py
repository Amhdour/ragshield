"""Simple Weaviate retrieval helper returning typed dictionaries."""

from __future__ import annotations

from urllib.parse import urlparse

import weaviate

from app.config import settings


def retrieve(query: str, top_k: int) -> list[dict[str, str]]:
    """Retrieve matching documents from RagDoc by BM25 query."""
    endpoint = urlparse(settings.WEAVIATE_URL)
    if not endpoint.hostname:
        raise RuntimeError(f"Invalid WEAVIATE_URL: {settings.WEAVIATE_URL}")

    if top_k < 1:
        raise RuntimeError("top_k must be >= 1")

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
            docs: list[dict[str, str]] = []
            for obj in response.objects:
                props = obj.properties
                docs.append(
                    {
                        "doc_id": str(props.get("doc_id", "")),
                        "category": str(props.get("category", "")),
                        "source": str(props.get("source", "")),
                        "content": str(props.get("content", "")),
                    }
                )
            return docs
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Retrieval failed. Ensure Weaviate is running and RagDoc has been ingested."
        ) from exc
