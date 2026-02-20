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


def chunk_text(content: str, chunk_size: int = 350, overlap: int = 50) -> list[tuple[int, int, str]]:
    """Split content into stable chunks by character window with offset metadata."""
    text = content.strip()
    if not text:
        return []

    chunks: list[tuple[int, int, str]] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(text), step):
        end = min(start + chunk_size, len(text))
        part = text[start:end]
        normalized = part.strip()
        if normalized:
            chunks.append((start, end, normalized))
        if end >= len(text):
            break
    return chunks


def build_chunk_records(parsed_doc: dict[str, str]) -> list[dict[str, str | int]]:
    """Build chunk records with stable chunk_id and auditable offset metadata per doc."""
    records: list[dict[str, str | int]] = []
    for idx, (start_char, end_char, chunk) in enumerate(chunk_text(parsed_doc["content"])):
        records.append(
            {
                "doc_id": parsed_doc["doc_id"],
                "chunk_id": f"{parsed_doc['doc_id']}::chunk::{idx}",
                "chunk_index": idx,
                "start_char": start_char,
                "end_char": end_char,
                "category": parsed_doc["category"],
                "source": parsed_doc["source"],
                "text": chunk,
            }
        )
    return records


def ingest(
    directory: Path,
    weaviate_url: str,
    collection_name: str = COLLECTION_NAME,
    use_embeddings: bool = True,
) -> None:
    """Create collection schema and ingest docs from directory."""
    if not directory.exists():
        raise RuntimeError(f"Input directory does not exist: {directory}")

    endpoint = urlparse(weaviate_url)
    if not endpoint.hostname:
        raise RuntimeError(f"Invalid WEAVIATE_URL: {weaviate_url}")

    chunk_records: list[dict[str, str | int]] = []
    for path in sorted(directory.glob("*.txt")):
        parsed_doc = parse_seeded_doc(path)
        chunk_records.extend(build_chunk_records(parsed_doc))

    vectors: list[list[float]] | None = None
    if use_embeddings:
        try:
            from app.embeddings import embed_texts

            vectors = embed_texts([str(record["text"]) for record in chunk_records])
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Embedding generation failed: {exc}. "
                "Set EMBEDDING_BASE_URL/EMBEDDING_MODEL/EMBEDDING_API_KEY (or legacy LITELLM_* vars) correctly, or run with --no-embeddings for BM25-only mode."
            ) from exc

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
                        name="chunk_id", data_type=weaviate.classes.config.DataType.TEXT
                    ),
                    weaviate.classes.config.Property(
                        name="chunk_index", data_type=weaviate.classes.config.DataType.INT
                    ),
                    weaviate.classes.config.Property(
                        name="start_char", data_type=weaviate.classes.config.DataType.INT
                    ),
                    weaviate.classes.config.Property(
                        name="end_char", data_type=weaviate.classes.config.DataType.INT
                    ),
                    weaviate.classes.config.Property(
                        name="category", data_type=weaviate.classes.config.DataType.TEXT
                    ),
                    weaviate.classes.config.Property(
                        name="source", data_type=weaviate.classes.config.DataType.TEXT
                    ),
                    weaviate.classes.config.Property(
                        name="text", data_type=weaviate.classes.config.DataType.TEXT
                    ),
                ],
            )

            collection = client.collections.get(collection_name)
            for idx, record in enumerate(chunk_records):
                if vectors is not None:
                    collection.data.insert(properties=record, vector=vectors[idx])
                else:
                    collection.data.insert(properties=record)
                print(f"Ingested {record['chunk_id']} ({record['category']})")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Ingestion failed. Ensure Weaviate is reachable and healthy.") from exc


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Ingest seeded docs into Weaviate")
    parser.add_argument("--input-dir", default="data/docs", type=Path)
    parser.add_argument("--weaviate-url", default="http://localhost:8080")
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip embedding generation and ingest in BM25-only mode.",
    )
    args = parser.parse_args()

    ingest(
        directory=args.input_dir,
        weaviate_url=args.weaviate_url,
        collection_name=args.collection,
        use_embeddings=not args.no_embeddings,
    )


if __name__ == "__main__":
    main()
