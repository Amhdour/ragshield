"""OPA policy gate helpers."""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ActionType = Literal["retrieval", "llm", "return_answer", "debug"]
DataScope = Literal["knowledge_base", "sensitive", "admin"]
RoleType = Literal["user", "admin"]


def _post_policy(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Post payload input to an OPA data endpoint and return decoded JSON."""
    base = settings.OPA_URL.rstrip("/")
    url = f"{base}{path}"
    response = httpx.post(url, json={"input": payload}, timeout=2.5)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("OPA response is not a JSON object")
    return data


def _parse_allow(result: Any) -> bool:
    """Parse allow endpoint result robustly into bool."""
    if isinstance(result, bool):
        return result
    if isinstance(result, dict) and "allow" in result:
        return bool(result.get("allow"))
    return bool(result)


def _parse_reasons(result: Any) -> list[str]:
    """Parse reasons endpoint result into list[str]."""
    if result is None:
        return []
    if isinstance(result, list):
        return [str(reason) for reason in result]
    if isinstance(result, dict):
        if "reasons" in result:
            nested = result.get("reasons")
            if isinstance(nested, list):
                return [str(reason) for reason in nested]
            if nested is not None:
                return [str(nested)]
        return [str(reason) for reason in result.keys()]
    return [str(result)]


def check_pre_action_policy(
    *,
    action: ActionType,
    requested_data_scope: DataScope,
    user_role: RoleType = "user",
    injection_suspected: bool = False,
    exfil_suspected: bool = False,
    response_is_refusal: bool = False,
) -> tuple[bool, list[str]]:
    """Return (allow, reasons) for pre-action policy checks before sensitive actions."""
    payload = {
        "action": action,
        "requested_data_scope": requested_data_scope,
        "user_role": user_role,
        "risk_flags": {
            "injection_suspected": bool(injection_suspected),
            "exfil_suspected": bool(exfil_suspected),
        },
        "response_is_refusal": bool(response_is_refusal),
    }
    try:
        allow_data = _post_policy("/v1/data/ragshield/allow_action", payload)
        reasons_data = _post_policy("/v1/data/ragshield/action_reasons", payload)
        allow = _parse_allow(allow_data.get("result"))
        reasons = _parse_reasons(reasons_data.get("result"))
        return allow, reasons
    except Exception as exc:  # noqa: BLE001
        logger.warning("OPA unavailable or error (%s); failing closed on pre-action gate.", exc)
        return False, ["Policy engine unavailable"]


def check_policy(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (allow, reasons) from OPA, failing closed when OPA is unavailable."""
    try:
        allow_data = _post_policy("/v1/data/ragshield/allow", payload)
        reasons_data = _post_policy("/v1/data/ragshield/reasons", payload)

        allow = _parse_allow(allow_data.get("result"))
        reasons = _parse_reasons(reasons_data.get("result"))
        return allow, reasons
    except Exception as exc:  # noqa: BLE001
        logger.warning("OPA unavailable or error (%s); failing closed.", exc)
        return False, ["Policy engine unavailable"]
