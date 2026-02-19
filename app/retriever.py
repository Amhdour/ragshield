"""Weaviate retrieval implementation for graph runtime."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import weaviate

from app.config import Settings


@dataclass(slots=True)
class WeaviateRetriever:
    """Retriever that fetches documents from Weaviate."""

    settings: Settings

    def retrieve(self, query: str, top_k: int = 4) -> list[str]:
        """Return retrieved document content for the supplied query."""
        endpoint = urlparse(self.settings.weaviate_url)
        if not endpoint.hostname:
            raise RuntimeError(f"Invalid WEAVIATE_URL: {self.settings.weaviate_url}")

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
                result = collection.query.bm25(query=query, limit=top_k)
                return [str(item.properties.get("content", "")) for item in result.objects]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Unable to retrieve from Weaviate. Check WEAVIATE_URL and ensure RagDoc is ingested."
            ) from exc
