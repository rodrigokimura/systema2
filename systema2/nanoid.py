"""Nano ID generator (self-contained, no external dependencies).

Uses the URL-safe alphabet ``a-zA-Z0-9_`` (63 chars) and a default
length of 21, giving ~125 bits of entropy. The implementation is
derandomised: each call draws ``length`` bytes from ``secrets`` and
maps them to alphabet characters via modulo.

``-`` is deliberately excluded from the alphabet so nano-ids never
start with a dash. A leading ``-`` is problematic for CLI positional
arguments (e.g. ``systema2 update <id>``) because Typer/Click would
interpret it as an option flag.
"""

from __future__ import annotations

import secrets
import string

_ALPHABET = string.ascii_lowercase + string.ascii_uppercase + string.digits + "_"
_DEFAULT_LENGTH = 21


def nanoid(length: int = _DEFAULT_LENGTH) -> str:
    """Generate a random nano-id string."""
    alphabet = _ALPHABET
    return "".join(
        alphabet[secrets.randbelow(len(alphabet))] for _ in range(length)
    )
