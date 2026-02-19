"""Environment-backed configuration for the ragshield application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


def _load_dotenv(dotenv_path: str = ".env") -> None:
    """Load key=value pairs from .env into the process environment if missing."""
    path = Path(dotenv_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _require_http_url(name: str, value: str) -> str:
    """Validate a URL value and return it unchanged when valid."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            f"Invalid {name}: {value!r}. Expected an absolute http(s) URL, e.g. http://localhost:8080"
        )
    return value


def _optional_http_url(name: str, value: str | None) -> str | None:
    """Validate an optional URL if provided."""
    if not value:
        return None
    return _require_http_url(name, value)


@dataclass(frozen=True)
class Settings:
    """Typed application settings loaded from environment variables."""

    LITELLM_BASE_URL: str
    LITELLM_MODEL: str
    LITELLM_API_KEY: str | None
    WEAVIATE_URL: str
    LANGFUSE_PUBLIC_KEY: str | None
    LANGFUSE_SECRET_KEY: str | None
    LANGFUSE_HOST: str | None
    OPA_URL: str
    TOP_K: int

    @property
    def litellm_base_url(self) -> str:
        """Backwards-compatible lowercase accessor."""
        return self.LITELLM_BASE_URL

    @property
    def litellm_model(self) -> str:
        """Backwards-compatible lowercase accessor."""
        return self.LITELLM_MODEL

    @property
    def openai_api_key(self) -> str | None:
        """Backwards-compatible accessor used by existing router code."""
        return self.LITELLM_API_KEY

    @property
    def weaviate_url(self) -> str:
        """Backwards-compatible lowercase accessor."""
        return self.WEAVIATE_URL

    @property
    def opa_url(self) -> str:
        """Backwards-compatible lowercase accessor."""
        return self.OPA_URL

    @property
    def langfuse_public_key(self) -> str | None:
        """Backwards-compatible lowercase accessor."""
        return self.LANGFUSE_PUBLIC_KEY

    @property
    def langfuse_secret_key(self) -> str | None:
        """Backwards-compatible lowercase accessor."""
        return self.LANGFUSE_SECRET_KEY

    @property
    def langfuse_host(self) -> str | None:
        """Backwards-compatible lowercase accessor."""
        return self.LANGFUSE_HOST


def load_settings() -> Settings:
    """Load settings from env vars with defaults and validation."""
    _load_dotenv()
    top_k_raw = os.getenv("TOP_K", "5")
    try:
        top_k = int(top_k_raw)
    except ValueError as exc:
        raise ValueError(f"Invalid TOP_K: {top_k_raw!r}. Expected integer >= 1.") from exc
    if top_k < 1:
        raise ValueError(f"Invalid TOP_K: {top_k}. Expected integer >= 1.")

    litellm_model = os.getenv("LITELLM_MODEL", "gpt-4o-mini").strip()
    if not litellm_model:
        raise ValueError("Invalid LITELLM_MODEL: value cannot be empty.")

    return Settings(
        LITELLM_BASE_URL=_require_http_url(
            "LITELLM_BASE_URL", os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
        ),
        LITELLM_MODEL=litellm_model,
        LITELLM_API_KEY=os.getenv("LITELLM_API_KEY") or None,
        WEAVIATE_URL=_require_http_url(
            "WEAVIATE_URL", os.getenv("WEAVIATE_URL", "http://localhost:8080")
        ),
        LANGFUSE_PUBLIC_KEY=os.getenv("LANGFUSE_PUBLIC_KEY") or None,
        LANGFUSE_SECRET_KEY=os.getenv("LANGFUSE_SECRET_KEY") or None,
        LANGFUSE_HOST=_optional_http_url("LANGFUSE_HOST", os.getenv("LANGFUSE_HOST")),
        OPA_URL=_require_http_url("OPA_URL", os.getenv("OPA_URL", "http://localhost:8181")),
        TOP_K=top_k,
    )


settings = load_settings()
