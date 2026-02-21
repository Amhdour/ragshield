"""List and validate embedding model IDs from an OpenAI-compatible embeddings endpoint."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any



def _extract_model_ids(payload: Any) -> list[str]:
    """Extract model ids from provider response payload."""
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if not isinstance(data, list):
        return []

    ids: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id.strip():
            ids.append(model_id.strip())
    return ids


def _models_url(base_url: str) -> str:
    """Build provider model-discovery URL from base URL."""
    return f"{base_url.rstrip('/')}/embeddings/models"


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="List OpenRouter embedding model IDs")
    parser.add_argument(
        "--contains",
        default="",
        help="Optional case-insensitive substring filter for model ids",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON payload for debugging",
    )
    parser.add_argument(
        "--check",
        default="",
        help="Exit 0 if this exact model id exists in the discovered models, otherwise exit 2",
    )
    args = parser.parse_args(argv)

    api_key = (os.getenv("EMBEDDING_API_KEY") or "").strip()
    if not api_key:
        print("Error: EMBEDDING_API_KEY is not set.")
        return 10

    base_url = (os.getenv("EMBEDDING_BASE_URL") or "https://openrouter.ai/api/v1").strip()
    if not base_url:
        base_url = "https://openrouter.ai/api/v1"

    try:
        import requests
    except Exception as exc:  # noqa: BLE001
        print(f"Error: requests dependency is unavailable: {exc}")
        return 11

    try:
        response = requests.get(
            _models_url(base_url),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        print(f"Error: failed to fetch embedding models from {base_url}: {exc}")
        return 11

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))

    all_ids = _extract_model_ids(payload)
    needle = args.contains.strip().lower()
    filtered_ids = [model_id for model_id in all_ids if needle in model_id.lower()] if needle else all_ids

    print(f"Total matching model IDs: {len(filtered_ids)}")
    print("Embedding model IDs (showing up to 25):")
    for model_id in filtered_ids[:25]:
        print(f"- {model_id}")
    if not filtered_ids:
        print("(no model IDs matched filter)")

    check_model = args.check.strip()
    if check_model:
        if check_model in all_ids:
            print(f"Check passed: model '{check_model}' is available.")
            return 0
        print(
            f"Check failed: model '{check_model}' was not found. "
            "Run scripts/check_openrouter_embeddings_models.py to inspect available IDs."
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
