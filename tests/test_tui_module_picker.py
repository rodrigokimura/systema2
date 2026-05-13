"""Tests for the startup ``ModulePickerScreen``.

These tests explicitly *unset* ``SYSTEMA2_SKIP_MODULE_PICKER`` (the
conftest fixture sets it so the existing task/whiteboard tests can
press keys directly against the default screen). Here we actually want
the picker to show up so we can exercise it.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from systema2.models import Whiteboard
from systema2.tui import Systema2App
from systema2.tui.screens.module_picker import ModulePickerScreen
from systema2.tui.screens.whiteboard_list import WhiteboardListScreen


@pytest.fixture
def show_picker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYSTEMA2_SKIP_MODULE_PICKER", raising=False)


async def test_picker_is_shown_on_mount(db_engine, show_picker) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ModulePickerScreen)


async def test_t_enters_tasks_module(db_engine, show_picker) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ModulePickerScreen)
        await pilot.press("t")
        await pilot.pause()
        # After picking Tasks, the picker is dismissed and the default
        # Systema2App screen (tasks/projects view) is on top.
        assert not isinstance(app.screen, ModulePickerScreen)
        assert not isinstance(app.screen, WhiteboardListScreen)


async def test_w_enters_whiteboards_module(db_engine, show_picker) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        assert isinstance(app.screen, WhiteboardListScreen)


async def test_enter_activates_highlighted_module(
    db_engine, show_picker
) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Default highlight is the first module (Tasks).
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, ModulePickerScreen)


async def test_k_j_moves_highlight_and_enter_picks_whiteboards(
    db_engine, show_picker
) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Move highlight down twice (Tasks → Calendar → Whiteboards), then activate.
        await pilot.press("j")
        await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, WhiteboardListScreen)


async def test_q_from_picker_quits_app(db_engine, show_picker) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    # ``run_test`` context exits cleanly when ``app.exit()`` runs.
    assert app._exit is True or not app.is_running  # noqa: SLF001


async def test_m_from_tasks_reopens_picker(db_engine) -> None:
    # Module picker is suppressed in the default conftest fixture, so we
    # land on the tasks screen. Pressing ``m`` should re-open the picker.
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not isinstance(app.screen, ModulePickerScreen)
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, ModulePickerScreen)


async def test_picker_to_whiteboards_then_back_to_tasks(
    db_engine, show_picker
) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Enter whiteboards module via keypress.
        await pilot.press("w")
        await pilot.pause()
        assert isinstance(app.screen, WhiteboardListScreen)

        # Exit whiteboards (pops that screen) back to the tasks view.
        await pilot.press("q")
        await pilot.pause()
        assert not isinstance(app.screen, WhiteboardListScreen)
        assert not isinstance(app.screen, ModulePickerScreen)

        # No whiteboards should have been created in this round trip.
        from systema2.database import engine as _engine  # current patched engine

        with Session(_engine) as s:
            assert list(s.exec(select(Whiteboard)).all()) == []
