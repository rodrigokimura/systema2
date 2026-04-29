"""Tests for the TUI colour theme."""

from __future__ import annotations

from systema2.tui import Systema2App


def test_theme_class_attr_is_tokyo_night() -> None:
    # Static attribute so the theme is discoverable without booting the app.
    assert Systema2App.THEME == "tokyo-night"


async def test_theme_applied_on_mount(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        # ``theme`` is set in on_mount from THEME.
        assert app.theme == "tokyo-night"
        # And the theme must resolve to a real, loaded Textual theme
        # (otherwise ``theme_variables`` would be empty).
        assert app.theme in app.available_themes
        assert app.theme_variables, "theme variables should be populated"
