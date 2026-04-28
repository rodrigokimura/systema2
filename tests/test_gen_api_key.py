"""Tests for the ``systema2 gen-api-key`` CLI command."""

from __future__ import annotations

import base64
import re

import pytest
from typer.testing import CliRunner

from systema2.cli import app as cli_app
from systema2.cli.auth import DEFAULT_BYTES

# ``secrets.token_urlsafe`` returns base64url without padding.
URL_SAFE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _decoded_len(token: str) -> int:
    # Re-add padding, decode, and measure the raw byte length so we can
    # assert entropy independently of the textual length.
    padded = token + "=" * (-len(token) % 4)
    return len(base64.urlsafe_b64decode(padded))


def test_gen_api_key_default(runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["gen-api-key"])
    assert result.exit_code == 0, result.output
    key = result.output.strip()
    assert URL_SAFE_RE.match(key), key
    assert _decoded_len(key) == DEFAULT_BYTES


def test_gen_api_key_custom_bytes(runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["gen-api-key", "--bytes", "48"])
    assert result.exit_code == 0, result.output
    key = result.output.strip()
    assert _decoded_len(key) == 48


def test_gen_api_key_rejects_weak_entropy(runner: CliRunner) -> None:
    # Below the 16-byte (~128-bit) floor Typer/Click should refuse.
    result = runner.invoke(cli_app, ["gen-api-key", "--bytes", "8"])
    assert result.exit_code != 0
    # Typer surfaces the ``min=`` constraint in the error message.
    combined = (result.output or "") + (result.stderr or "")
    assert "16" in combined


def test_gen_api_key_export_shell_snippet(runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["gen-api-key", "--export"])
    assert result.exit_code == 0, result.output
    line = result.output.strip()
    assert line.startswith("export SYSTEMA2_API_KEY=")
    key = line.split("=", 1)[1]
    assert URL_SAFE_RE.match(key), key
    assert _decoded_len(key) == DEFAULT_BYTES


def test_gen_api_key_is_unique(runner: CliRunner) -> None:
    # Two consecutive invocations must return different keys; this would
    # catch a regression where someone hard-codes the token or swaps in
    # a non-CSPRNG source.
    keys = {
        runner.invoke(cli_app, ["gen-api-key"]).output.strip()
        for _ in range(5)
    }
    assert len(keys) == 5
