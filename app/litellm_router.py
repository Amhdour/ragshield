"""LiteLLM model routing implementation."""

from __future__ import annotations

from dataclasses import dataclass

from litellm import completion

from app.config import Settings


@dataclass(slots=True)
class LiteLLMRouter:
    """Routes prompts through LiteLLM using configured model."""

    settings: Settings

    def generate(self, prompt: str) -> str:
        """Generate response text from LiteLLM."""
        if not self.settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your environment to enable generation."
            )

        try:
            response = completion(
                model=self.settings.litellm_model,
                messages=[{"role": "user", "content": prompt}],
                api_base=self.settings.litellm_base_url,
                api_key=self.settings.openai_api_key,
            )
            return str(response.choices[0].message.content)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "LiteLLM request failed. Verify LITELLM_BASE_URL, model routing, and credentials."
            ) from exc
