"""Runtime configuration (pydantic-settings).

All configuration is read from the environment with the ``SYSTEMA2_``
prefix:

SYSTEMA2_MODE
    One of ``local`` (default), ``client``, ``server``.
    - ``local``: all operations hit the local SQLite database directly.
    - ``client``: CLI/TUI proxy operations over HTTP to a running server.
    - ``server``: same as ``local`` for CRUD, and exposes ``systema2 serve``
      to run the FastAPI app that ``client`` mode talks to.

SYSTEMA2_API_URL
    Base URL used by ``client`` mode. Defaults to ``http://127.0.0.1:8000``.

SYSTEMA2_HOST / SYSTEMA2_PORT
    Bind address for ``systema2 serve``. Default ``127.0.0.1:8000``.

SYSTEMA2_API_KEY
    Shared secret used to authenticate ``client`` → ``server`` calls.

    - In ``server`` mode: if set, every request to ``/tasks`` and
      ``/projects`` must present this value in the ``X-API-Key`` header
      (or an ``Authorization: Bearer <key>`` header). If unset, the
      server runs without authentication (useful for local/dev).
    - In ``client`` mode: if set, the value is sent as ``X-API-Key`` on
      every outgoing request.

The module exposes both the :class:`Settings` model (``get_settings()``)
and small shim functions (``get_mode``/``get_api_url``/``get_host``/
``get_port``/``get_api_key``) that re-read the environment on each call.
Tests rely on this "live" behaviour (they use ``monkeypatch.setenv``
between calls), so no settings instance is cached.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(str, Enum):
    LOCAL = "local"
    CLIENT = "client"
    SERVER = "server"


DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class Settings(BaseSettings):
    """Typed view over ``SYSTEMA2_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="SYSTEMA2_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    mode: Mode = Field(default=Mode.LOCAL)
    api_url: str = Field(default=DEFAULT_API_URL)
    host: str = Field(default=DEFAULT_HOST)
    port: int = Field(default=DEFAULT_PORT)
    api_key: str | None = Field(default=None)

    # --- normalizers ----------------------------------------------------

    @field_validator("mode", mode="before")
    @classmethod
    def _normalize_mode(cls, v: object) -> object:
        # Accept any case / surrounding whitespace, mirroring the old
        # hand-rolled ``get_mode`` behaviour.
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("api_url", mode="after")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, v: object) -> object:
        # Treat an empty or whitespace-only env var as "not configured".
        if isinstance(v, str) and not v.strip():
            return None
        if isinstance(v, str):
            return v.strip()
        return v


def get_settings() -> Settings:
    """Build a fresh :class:`Settings` from the current environment.

    Each call re-reads ``os.environ`` so that tests using
    ``monkeypatch.setenv`` see their changes reflected immediately.
    Invalid values are re-raised as :class:`ValueError` with the legacy
    ``Invalid SYSTEMA2_MODE=...`` message, which the e2e tests assert on.
    """
    try:
        return Settings()
    except ValidationError as exc:
        for err in exc.errors():
            if err.get("loc") == ("mode",):
                valid = ", ".join(m.value for m in Mode)
                raw = err.get("input")
                raise ValueError(
                    f"Invalid SYSTEMA2_MODE={raw!r}. Valid values: {valid}."
                ) from exc
        raise


# ---------------------------------------------------------------------------
# Back-compat getters (used throughout the codebase and tests).
# ---------------------------------------------------------------------------


def get_mode() -> Mode:
    return get_settings().mode


def get_api_url() -> str:
    return get_settings().api_url


def get_host() -> str:
    return get_settings().host


def get_port() -> int:
    return get_settings().port


def get_api_key() -> str | None:
    return get_settings().api_key
