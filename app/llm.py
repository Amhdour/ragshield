"""LiteLLM wrapper for chat generation."""

from __future__ import annotations

from typing import Any

from app.config import settings


def generate(messages: list[dict[str, Any]], request_id: str | None = None) -> str:
    """Generate a model response via LiteLLM using environment-backed config."""
    if not messages:
        raise RuntimeError("LiteLLM generation failed for model unknown at provider unknown: messages cannot be empty.")

    provider = settings.LITELLM_BASE_URL
    model = settings.LITELLM_MODEL

    try:
        from litellm import completion
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"LiteLLM generation failed for model {model} at provider {provider}: "
            "litellm package is not installed. Install project dependencies first."
        ) from exc

    request_kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "api_base": provider,
    }
    if settings.LITELLM_API_KEY:
        request_kwargs["api_key"] = settings.LITELLM_API_KEY
    if request_id:
        request_kwargs["metadata"] = {"request_id": request_id}

    try:
        response = completion(**request_kwargs)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("received empty response content")
        return str(content)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"LiteLLM generation failed for model {model} at provider {provider}: {exc}"
        ) from exc
