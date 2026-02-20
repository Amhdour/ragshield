"""Quick smoke test for structured-output behavior via /chat."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _validate_payload_shape(payload: dict) -> bool:
    """Minimal payload validation without requiring runtime extras."""
    required = {"answer", "citations", "confidence", "refusal_reason"}
    if not isinstance(payload, dict) or not required.issubset(payload.keys()):
        return False
    if payload.get("confidence") not in {"low", "med", "high"}:
        return False
    if not isinstance(payload.get("citations"), list):
        return False
    return True


def _structured_output_status(log_file: Path) -> str:
    """Infer whether json_schema was used or fallback occurred from app logs."""
    if not log_file.exists():
        return "unknown (log file not found)"

    text = log_file.read_text(encoding="utf-8", errors="ignore")
    if "structured_output_fallback" in text:
        return "fell_back_to_prompt_only"
    if "structured_output_mode=json_schema" in text:
        return "json_schema_used"
    if "structured_output_mode=prompt_only" in text:
        return "prompt_only"
    return "unknown (no structured-output markers found)"


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Smoke test /chat structured-output behavior")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--question", default="What is Ragshield?")
    parser.add_argument("--log-file", default="/tmp/uvicorn.log")
    args = parser.parse_args()

    try:
        import requests
    except Exception as exc:  # noqa: BLE001
        print(f"requests unavailable: {exc}")
        return 2

    url = f"{args.base_url.rstrip('/')}/chat"
    try:
        response = requests.post(url, json={"query": args.question}, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        print(f"/chat request failed: {exc}")
        return 3

    if not isinstance(payload, dict):
        print("invalid payload: response is not a JSON object")
        return 4

    valid = _validate_payload_shape(payload)
    print(f"valid_answer_payload_json={valid}")
    print(f"structured_output_status={_structured_output_status(Path(args.log_file))}")
    print(json.dumps(payload, indent=2))

    return 0 if valid else 5


if __name__ == "__main__":
    raise SystemExit(main())
