"""`systema2 gen-api-key` command.

Generates a cryptographically strong, URL-safe token suitable for use
as ``SYSTEMA2_API_KEY``. Uses :func:`secrets.token_urlsafe`, which pulls
from the OS CSPRNG.
"""

from __future__ import annotations

import secrets

import typer

# 32 random bytes → ~43 URL-safe characters. Comfortably above the
# ~128-bit bar recommended for shared secrets.
DEFAULT_BYTES = 32
MIN_BYTES = 16


def gen_api_key(
    nbytes: int = typer.Option(
        DEFAULT_BYTES,
        "--bytes",
        "-b",
        min=MIN_BYTES,
        help=(
            "Entropy in bytes (minimum 16 \u2248 128 bits). "
            f"Default {DEFAULT_BYTES} \u2248 256 bits."
        ),
    ),
    export: bool = typer.Option(
        False,
        "--export",
        "-e",
        help="Print as a shell snippet: export SYSTEMA2_API_KEY=<key>",
    ),
) -> None:
    """Generate a cryptographically strong API key.

    The value is written to stdout on its own line so it can be captured
    with shell substitution, e.g.::

        export SYSTEMA2_API_KEY="$(systema2 gen-api-key)"
    """
    key = secrets.token_urlsafe(nbytes)
    if export:
        typer.echo(f"export SYSTEMA2_API_KEY={key}")
    else:
        typer.echo(key)
