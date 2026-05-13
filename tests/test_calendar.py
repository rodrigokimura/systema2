"""Tests for the TUI calendar module."""

from __future__ import annotations

from datetime import date

from systema2.tui import Systema2App
from systema2.tui.screens.calendar import CalendarScreen
from textual.widgets import ListView, Static

from systema2.tui.screens.module_picker import ModulePickerScreen


async def test_c_opens_calendar_screen(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.screen, CalendarScreen)


async def test_calendar_shows_current_month(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(CalendarScreen())
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CalendarScreen)
        header = screen.query_one("#calendar_header", Static)
        today = date.today()
        assert today.strftime("%B %Y") in header.content


async def test_h_and_l_navigate_months(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(CalendarScreen())
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CalendarScreen)
        header = screen.query_one("#calendar_header", Static)
        month_before = header.content

        await pilot.press("l")
        await pilot.pause()
        month_after = header.content
        assert month_after != month_before

        await pilot.press("h")
        await pilot.pause()
        assert header.content == month_before


async def test_sidebar_switch_to_yearly(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(CalendarScreen())
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CalendarScreen)

        # Select 'Yearly' from sidebar (index 2)
        lv = screen.query_one("#view_list")
        lv.index = 2
        item = list(lv.children)[2]
        lv.post_message(ListView.Selected(lv, item, 2))
        await pilot.pause()

        header = screen.query_one("#calendar_header", Static)
        assert str(date.today().year) == header.content.strip()


async def test_escape_closes_calendar(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(CalendarScreen())
        await pilot.pause()
        assert isinstance(app.screen, CalendarScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, CalendarScreen)
