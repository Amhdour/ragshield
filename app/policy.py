"""OPA policy gate helpers."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _post_policy(path: str, payload: dict[str, Any]) -> Any:
    """Post payload input to an OPA data endpoint and return result."""
    base = settings.OPA_URL.rstrip("/")
    url = f"{base}{path}"
    response = httpx.post(url, json={"input": payload}, timeout=2.5)
    response.raise_for_status()
    return response.json().get("result")


def check_policy(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (allow, reasons) from OPA, failing open when OPA is unavailable."""
    try:
        allow_result = _post_policy("/v1/data/ragshield/allow", payload)
        reasons_result = _post_policy("/v1/data/ragshield/reasons", payload)

        allow = bool(allow_result)
        reasons: list[str]
        if isinstance(reasons_result, list):
            reasons = [str(reason) for reason in reasons_result]
        elif reasons_result is None:
            reasons = []
        else:
            reasons = [str(reasons_result)]
        return allow, reasons
    except Exception as exc:  # noqa: BLE001
        logger.warning("OPA unavailable or error (%s); failing open.", exc)
        return True, []
