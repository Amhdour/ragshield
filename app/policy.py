"""OPA policy-gate integration."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings


@dataclass(slots=True)
class OPAPolicyGate:
    """Queries OPA for allow/deny decisions."""

    settings: Settings

    def allow(self, query: str, context: list[str], response: str) -> bool:
        """Return True if OPA policy allows this response."""
        input_payload = {"input": {"query": query, "context": context, "response": response}}
        policy_url = f"{self.settings.opa_url.rstrip('/')}/{self.settings.opa_policy_path.lstrip('/')}"
        try:
            result = httpx.post(policy_url, json=input_payload, timeout=5.0)
            result.raise_for_status()
            return bool(result.json().get("result", False))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "OPA policy check failed. Ensure OPA is running and OPA_POLICY_PATH is valid."
            ) from exc
