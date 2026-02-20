"""LiteLLM wrapper for chat generation with structured output support."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _answer_payload_json_schema() -> dict[str, Any]:
    """Build JSON Schema from AnswerPayload model (best effort)."""
    from app.schema import AnswerPayload

    schema = AnswerPayload.model_json_schema()
    return {
        "name": "answer_payload",
        "schema": schema,
        "strict": True,
    }


def _extract_content(response: Any) -> str:
    """Extract content from LiteLLM response object safely."""
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("received empty response content")
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return str(content)


def generate(messages: list[dict[str, Any]], request_id: str | None = None) -> str:
    """Generate a model response via LiteLLM using environment-backed config."""
    if not messages:
        raise RuntimeError(
            "LiteLLM generation failed for model unknown at provider unknown: messages cannot be empty."
        )

    provider = settings.LITELLM_BASE_URL
    model = settings.LITELLM_MODEL or settings.DEFAULT_MODEL

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

    mode = settings.STRUCTURED_OUTPUT_MODE
    use_json_schema = mode in {"auto", "json_schema"}

    if use_json_schema:
        request_kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": _answer_payload_json_schema(),
        }

    try:
        response = completion(**request_kwargs)
        logger.info("structured_output_mode=%s", "json_schema" if use_json_schema else "prompt_only")
        content = _extract_content(response)
        return content
    except Exception as exc:  # noqa: BLE001
        if use_json_schema and mode == "auto":
            logger.warning("structured_output_mode=prompt_only_fallback reason=%s", exc)
            fallback_kwargs = dict(request_kwargs)
            fallback_kwargs.pop("response_format", None)
            try:
                response = completion(**fallback_kwargs)
                content = _extract_content(response)
                return content
            except Exception as fallback_exc:  # noqa: BLE001
                raise RuntimeError(
                    f"LiteLLM generation failed for model {model} at provider {provider}: {fallback_exc}"
                ) from fallback_exc

        raise RuntimeError(
            f"LiteLLM generation failed for model {model} at provider {provider}: {exc}"
        ) from exc
