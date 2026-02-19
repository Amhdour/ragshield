"""Ingest seeded documents into a Weaviate collection."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

import weaviate

COLLECTION_NAME = "RagDoc"


def parse_seeded_doc(path: Path) -> dict[str, str]:
    """Parse seeded key/value file content into a document payload."""
    parsed: dict[str, str] = {"doc_id": "", "category": "", "source": "", "content": ""}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key_clean = key.strip().lower()
        if key_clean in parsed:
            parsed[key_clean] = value.strip()

    if not all(parsed.values()):
        raise RuntimeError(
            f"Invalid doc format in {path}. Expected doc_id/category/source/content lines."
        )
    return parsed


def ingest(directory: Path, weaviate_url: str, collection_name: str = COLLECTION_NAME) -> None:
    """Create collection schema and ingest docs from directory."""
    if not directory.exists():
        raise RuntimeError(f"Input directory does not exist: {directory}")

    endpoint = urlparse(weaviate_url)
    if not endpoint.hostname:
        raise RuntimeError(f"Invalid WEAVIATE_URL: {weaviate_url}")

    try:
        with weaviate.connect_to_custom(
            http_host=endpoint.hostname,
            http_port=endpoint.port or 8080,
            http_secure=endpoint.scheme == "https",
            grpc_host=endpoint.hostname,
            grpc_port=50051,
            grpc_secure=False,
        ) as client:
            if client.collections.exists(collection_name):
                client.collections.delete(collection_name)

            client.collections.create(
                name=collection_name,
                vectorizer_config=weaviate.classes.config.Configure.Vectorizer.none(),
                properties=[
                    weaviate.classes.config.Property(
                        name="doc_id", data_type=weaviate.classes.config.DataType.TEXT
                    ),
                    weaviate.classes.config.Property(
                        name="category", data_type=weaviate.classes.config.DataType.TEXT
                    ),
                    weaviate.classes.config.Property(
                        name="source", data_type=weaviate.classes.config.DataType.TEXT
                    ),
                    weaviate.classes.config.Property(
                        name="content", data_type=weaviate.classes.config.DataType.TEXT
                    ),
                ],
            )

            collection = client.collections.get(collection_name)
            for path in sorted(directory.glob("*.txt")):
                doc = parse_seeded_doc(path)
                collection.data.insert(doc)
                print(f"Ingested {path.name} ({doc['category']})")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Ingestion failed. Ensure Weaviate is reachable and healthy.") from exc


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Ingest seeded docs into Weaviate")
    parser.add_argument("--input-dir", default="data/docs", type=Path)
    parser.add_argument("--weaviate-url", default="http://localhost:8080")
    parser.add_argument("--collection", default=COLLECTION_NAME)
    args = parser.parse_args()

    ingest(args.input_dir, args.weaviate_url, args.collection)


if __name__ == "__main__":
    main()
