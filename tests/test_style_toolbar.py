"""Tests for the whiteboard style toolbar."""

from __future__ import annotations

from systema2 import whiteboard_services as wbs
from systema2.models import BoxCreate, WhiteboardCreate
from systema2.tui import Systema2App
from systema2.tui.screens.whiteboard import WhiteboardScreen
from textual.widgets import Button, Select


async def test_toolbar_is_hidden_by_default(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="tb"))
    wbs.create_box_std(BoxCreate(whiteboard_id=wb.id, x=5, y=5, label="b"))

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, WhiteboardScreen)

        toolbar = screen.query_one("#style_toolbar")
        assert toolbar.display is False


async def test_b_toggles_toolbar(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="tb"))
    wbs.create_box_std(BoxCreate(whiteboard_id=wb.id, x=5, y=5, label="b"))

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, WhiteboardScreen)
        toolbar = screen.query_one("#style_toolbar")

        # initially hidden
        assert toolbar.display is False

        await pilot.press("b")
        await pilot.pause()
        assert toolbar.display is True

        await pilot.press("b")
        await pilot.pause()
        assert toolbar.display is False


async def test_toolbar_reflects_selected_box_style(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="tb"))
    box = wbs.create_box_std(
        BoxCreate(
            whiteboard_id=wb.id,
            x=5,
            y=5,
            label="b",
            border_style="bold red",
            fill_style="on green",
        )
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, WhiteboardScreen)

        await pilot.press("b")
        await pilot.pause()

        sel_border = screen.query_one("#sel_border", Select)
        sel_fill = screen.query_one("#sel_fill", Select)

        # Change style through the toolbar and verify DB is updated.
        sel_border.value = "bold blue"
        await pilot.pause()
        refreshed = wbs.get_box_std(box.id)
        assert refreshed is not None
        assert refreshed.border_style == "bold blue"

        sel_fill.value = "on yellow"
        await pilot.pause()
        refreshed = wbs.get_box_std(box.id)
        assert refreshed is not None
        assert refreshed.fill_style == "on yellow"


async def test_select_border_updates_box(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="tb"))
    box = wbs.create_box_std(
        BoxCreate(
            whiteboard_id=wb.id,
            x=5,
            y=5,
            label="b",
            border_style="bold white",
        )
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, WhiteboardScreen)

        await pilot.press("b")
        await pilot.pause()

        sel = screen.query_one("#sel_border", Select)
        # We can trigger a change by directly setting value.
        sel.value = "bold blue"
        await pilot.pause()

        refreshed = wbs.get_box_std(box.id)
        assert refreshed is not None
        assert refreshed.border_style == "bold blue"


async def test_clear_fill_button_clears_fill(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="tb"))
    box = wbs.create_box_std(
        BoxCreate(
            whiteboard_id=wb.id,
            x=5,
            y=5,
            label="b",
            fill_style="on yellow",
        )
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, WhiteboardScreen)

        await pilot.press("b")
        await pilot.pause()

        btn = screen.query_one("#btn_clear", Button)
        btn.press()
        await pilot.pause()

        refreshed = wbs.get_box_std(box.id)
        assert refreshed is not None
        assert refreshed.fill_style is None
