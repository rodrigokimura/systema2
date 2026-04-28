"""API-key authentication for ``server`` mode.

The server enforces authentication when ``SYSTEMA2_API_KEY`` is set in
its environment. Clients authenticate by sending the shared secret in
either:

- ``X-API-Key: <key>``, or
- ``Authorization: Bearer <key>``.

If ``SYSTEMA2_API_KEY`` is unset the dependency is a no-op, which keeps
the default local/dev experience frictionless.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from systema2.config import get_api_key

API_KEY_HEADER = "X-API-Key"


def _extract_presented_key(
    x_api_key: str | None, authorization: str | None
) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
    return None


def require_api_key(
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI dependency that enforces ``SYSTEMA2_API_KEY`` when set.

    Raises ``401`` when the header is missing and ``403`` when it is
    present but incorrect. When no API key is configured on the server,
    the dependency allows the request through.
    """
    expected = get_api_key()
    if expected is None:
        return

    presented = _extract_presented_key(x_api_key, authorization)
    if presented is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )
    # Constant-time comparison to avoid timing side-channels.
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Invalid API key"
        )
