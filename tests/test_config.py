"""Tests for the pydantic-settings based ``systema2.config`` module."""

from __future__ import annotations

import pytest

from systema2.config import (
    DEFAULT_API_URL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    Mode,
    Settings,
    get_api_key,
    get_api_url,
    get_host,
    get_mode,
    get_port,
    get_settings,
)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "SYSTEMA2_MODE",
        "SYSTEMA2_API_URL",
        "SYSTEMA2_HOST",
        "SYSTEMA2_PORT",
        "SYSTEMA2_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    s = get_settings()
    assert s.mode is Mode.LOCAL
    assert s.api_url == DEFAULT_API_URL
    assert s.host == DEFAULT_HOST
    assert s.port == DEFAULT_PORT
    assert s.api_key is None


def test_env_overrides_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMA2_MODE", "server")
    monkeypatch.setenv("SYSTEMA2_API_URL", "https://example.com/")
    monkeypatch.setenv("SYSTEMA2_HOST", "0.0.0.0")  # noqa: S104
    monkeypatch.setenv("SYSTEMA2_PORT", "9001")
    monkeypatch.setenv("SYSTEMA2_API_KEY", "hunter2")

    s = get_settings()
    assert s.mode is Mode.SERVER
    # Trailing slash stripped by the validator.
    assert s.api_url == "https://example.com"
    assert s.host == "0.0.0.0"  # noqa: S104
    assert s.port == 9001
    assert s.api_key == "hunter2"

    # And the legacy shims agree.
    assert get_mode() is Mode.SERVER
    assert get_api_url() == "https://example.com"
    assert get_host() == "0.0.0.0"  # noqa: S104
    assert get_port() == 9001
    assert get_api_key() == "hunter2"


def test_mode_is_case_insensitive_and_trimmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYSTEMA2_MODE", "  CLIENT  ")
    assert get_mode() is Mode.CLIENT


def test_invalid_mode_preserves_legacy_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The e2e tests assert on this exact prefix; don't regress it.
    monkeypatch.setenv("SYSTEMA2_MODE", "bogus")
    with pytest.raises(ValueError, match=r"^Invalid SYSTEMA2_MODE='bogus'"):
        get_settings()


def test_invalid_port_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMA2_PORT", "not-a-number")
    # pydantic raises its own ValidationError; we don't remap it.
    with pytest.raises(Exception):  # noqa: B017
        get_settings()


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_api_key_becomes_none(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("SYSTEMA2_API_KEY", value)
    assert get_api_key() is None


def test_api_key_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMA2_API_KEY", "  padded  ")
    assert get_api_key() == "padded"


def test_api_url_trailing_slash_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYSTEMA2_API_URL", "http://srv:8000///")
    assert get_api_url() == "http://srv:8000"


def test_get_settings_rereads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Each call must observe the current env so test isolation works
    # (we rely on ``monkeypatch.setenv`` between calls everywhere else).
    monkeypatch.setenv("SYSTEMA2_MODE", "client")
    assert get_settings().mode is Mode.CLIENT
    monkeypatch.setenv("SYSTEMA2_MODE", "server")
    assert get_settings().mode is Mode.SERVER


def test_settings_ignores_unknown_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Forward-compat: an unrelated ``SYSTEMA2_*`` var must not blow up.
    monkeypatch.setenv("SYSTEMA2_FUTURE_FLAG", "1")
    s = Settings()
    assert s.mode is Mode.LOCAL
