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
    DEFAULT_MODEL: str
    LITELLM_MODEL: str
    STRUCTURED_OUTPUT_MODE: str
    EMBEDDING_MODEL: str
    LITELLM_API_KEY: str | None
    WEAVIATE_URL: str
    LANGFUSE_PUBLIC_KEY: str | None
    LANGFUSE_SECRET_KEY: str | None
    LANGFUSE_HOST: str | None
    RAGSHIELD_ENV: str
    DEBUG_TRACE: bool
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
    def default_model(self) -> str:
        """Backwards-compatible lowercase accessor."""
        return self.DEFAULT_MODEL

    @property
    def structured_output_mode(self) -> str:
        """Backwards-compatible lowercase accessor."""
        return self.STRUCTURED_OUTPUT_MODE

    @property
    def embedding_model(self) -> str:
        """Backwards-compatible lowercase accessor."""
        return self.EMBEDDING_MODEL

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

    @property
    def ragshield_env(self) -> str:
        """Backwards-compatible lowercase accessor."""
        return self.RAGSHIELD_ENV

    @property
    def debug_trace(self) -> bool:
        """Backwards-compatible lowercase accessor."""
        return self.DEBUG_TRACE


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

    default_model = (os.getenv("DEFAULT_MODEL", "gpt-4o-mini") or "gpt-4o-mini").strip()
    if not default_model:
        raise ValueError("Invalid DEFAULT_MODEL: value cannot be empty.")

    litellm_model = (os.getenv("LITELLM_MODEL") or default_model).strip()
    if not litellm_model:
        raise ValueError("Invalid LITELLM_MODEL: value cannot be empty.")

    structured_output_mode = (os.getenv("STRUCTURED_OUTPUT_MODE", "auto") or "auto").strip().lower()
    if structured_output_mode not in {"auto", "json_schema", "prompt_only"}:
        raise ValueError(
            "Invalid STRUCTURED_OUTPUT_MODE: expected one of 'auto', 'json_schema', 'prompt_only'."
        )

    embedding_model = (os.getenv("EMBEDDING_MODEL", "text-embedding-3-small") or "text-embedding-3-small").strip()
    if not embedding_model:
        raise ValueError("Invalid EMBEDDING_MODEL: value cannot be empty.")

    ragshield_env = (os.getenv("RAGSHIELD_ENV", "dev") or "dev").strip().lower()
    if ragshield_env not in {"dev", "prod"}:
        raise ValueError("Invalid RAGSHIELD_ENV: expected 'dev' or 'prod'.")

    debug_trace_raw = (os.getenv("DEBUG_TRACE", "false") or "false").strip().lower()
    if debug_trace_raw not in {"1", "0", "true", "false", "yes", "no"}:
        raise ValueError("Invalid DEBUG_TRACE: expected true/false.")
    debug_trace = debug_trace_raw in {"1", "true", "yes"}

    return Settings(
        LITELLM_BASE_URL=_require_http_url(
            "LITELLM_BASE_URL", os.getenv("LITELLM_BASE_URL", "http://litellm:4000")
        ),
        DEFAULT_MODEL=default_model,
        LITELLM_MODEL=litellm_model,
        STRUCTURED_OUTPUT_MODE=structured_output_mode,
        EMBEDDING_MODEL=embedding_model,
        LITELLM_API_KEY=os.getenv("LITELLM_API_KEY") or None,
        WEAVIATE_URL=_require_http_url(
            "WEAVIATE_URL", os.getenv("WEAVIATE_URL", "http://localhost:8080")
        ),
        LANGFUSE_PUBLIC_KEY=os.getenv("LANGFUSE_PUBLIC_KEY") or None,
        LANGFUSE_SECRET_KEY=os.getenv("LANGFUSE_SECRET_KEY") or None,
        LANGFUSE_HOST=_optional_http_url(
            "LANGFUSE_HOST", os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        ),
        RAGSHIELD_ENV=ragshield_env,
        DEBUG_TRACE=debug_trace,
        OPA_URL=_require_http_url("OPA_URL", os.getenv("OPA_URL", "http://localhost:8181")),
        TOP_K=top_k,
    )


settings = load_settings()
