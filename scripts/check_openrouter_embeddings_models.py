"""List OpenRouter embedding models and filter by substring."""

from __future__ import annotations

import argparse
import os
from typing import Any

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/embeddings/models"


def _extract_model_ids(payload: Any) -> list[str]:
    """Extract model ids from OpenRouter response payload."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    ids: list[str] = []
    for item in data:
        if isinstance(item, dict):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                ids.append(model_id.strip())
    return ids


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="List OpenRouter embedding model IDs")
    parser.add_argument(
        "--contains",
        default="",
        help="Optional case-insensitive substring filter for model ids",
    )
    args = parser.parse_args(argv)

    api_key = os.getenv("EMBEDDING_API_KEY") or ""
    if not api_key:
        print(
            "Error: EMBEDDING_API_KEY is not set. "
            "Set EMBEDDING_API_KEY to call OpenRouter embeddings models endpoint."
        )
        return 2

    try:
        import requests
    except Exception as exc:  # noqa: BLE001
        print(f"Error: requests dependency is unavailable: {exc}")
        return 4

    try:
        response = requests.get(
            OPENROUTER_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"Error: failed to fetch OpenRouter embedding models: {exc}")
        return 3

    ids = _extract_model_ids(response.json())
    needle = args.contains.strip().lower()
    if needle:
        ids = [model_id for model_id in ids if needle in model_id.lower()]

    print("OpenRouter embedding model IDs (showing up to 25):")
    for model_id in ids[:25]:
        print(f"- {model_id}")

    if not ids:
        print("(no model IDs matched filter)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
