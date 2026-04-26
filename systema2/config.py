"""Runtime configuration driven by environment variables.

Environment variables
---------------------
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
"""

from __future__ import annotations

import os
from enum import Enum


class Mode(str, Enum):
    LOCAL = "local"
    CLIENT = "client"
    SERVER = "server"


DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def get_mode() -> Mode:
    raw = os.environ.get("SYSTEMA2_MODE", Mode.LOCAL.value).strip().lower()
    try:
        return Mode(raw)
    except ValueError as exc:
        valid = ", ".join(m.value for m in Mode)
        raise ValueError(
            f"Invalid SYSTEMA2_MODE={raw!r}. Valid values: {valid}."
        ) from exc


def get_api_url() -> str:
    return os.environ.get("SYSTEMA2_API_URL", DEFAULT_API_URL).rstrip("/")


def get_host() -> str:
    return os.environ.get("SYSTEMA2_HOST", DEFAULT_HOST)


def get_port() -> int:
    return int(os.environ.get("SYSTEMA2_PORT", str(DEFAULT_PORT)))
