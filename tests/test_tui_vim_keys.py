"""Tests for vim-style keybindings in the Textual TUI."""

from __future__ import annotations

from sqlmodel import Session, select
from textual.widgets import DataTable

from systema2.models import Project, Task
from systema2.tui import Systema2App


# ---------------------------------------------------------------------------
# Navigation: j / k / g / G
# ---------------------------------------------------------------------------


def _seed_tasks(db_engine, n: int) -> None:
    with Session(db_engine) as s:
        for i in range(n):
            s.add(Task(title=f"task {i}"))
        s.commit()


async def test_j_moves_cursor_down(db_engine) -> None:
    _seed_tasks(db_engine, 3)
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        table.focus()
        await pilot.pause()
        assert table.cursor_row == 0
        await pilot.press("j")
        await pilot.pause()
        assert table.cursor_row == 1
        await pilot.press("j")
        await pilot.pause()
        assert table.cursor_row == 2


async def test_k_moves_cursor_up(db_engine) -> None:
    _seed_tasks(db_engine, 3)
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        table.focus()
        table.move_cursor(row=2)
        await pilot.pause()
        await pilot.press("k")
        await pilot.pause()
        assert table.cursor_row == 1
        await pilot.press("k")
        await pilot.pause()
        assert table.cursor_row == 0


async def test_G_jumps_to_bottom_and_g_to_top(db_engine) -> None:
    _seed_tasks(db_engine, 5)
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        table.focus()
        await pilot.pause()
        await pilot.press("G")  # shift+g -> bottom
        await pilot.pause()
        assert table.cursor_row == 4
        await pilot.press("g")  # top
        await pilot.pause()
        assert table.cursor_row == 0


# ---------------------------------------------------------------------------
# Space toggles completed flag
# ---------------------------------------------------------------------------


async def test_space_toggles_completed(db_engine) -> None:
    with Session(db_engine) as s:
        s.add(Task(title="toggle me"))
        s.commit()

    # First press: not-done -> done.
    async with Systema2App().run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    with Session(db_engine) as s:
        tasks = list(s.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].completed is True

    # Second press (fresh app instance): done -> not-done.
    async with Systema2App().run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    with Session(db_engine) as s:
        tasks = list(s.exec(select(Task)).all())
    assert tasks[0].completed is False


async def test_space_without_selection_is_safe(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()
        # No crash, no modal pushed.
        assert len(app.screen_stack) == 1


# ---------------------------------------------------------------------------
# ctrl+w switches panes (sidebar <-> table)
# ---------------------------------------------------------------------------


async def test_ctrl_w_switches_focus_between_panes(db_engine) -> None:
    with Session(db_engine) as s:
        s.add(Project(name="p"))
        s.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        sidebar = app.query_one("#project_list")
        # Start by focusing the table explicitly for a deterministic origin.
        table.focus()
        await pilot.pause()
        assert app.focused is table

        await pilot.press("ctrl+w")
        await pilot.pause()
        assert app.focused is sidebar

        await pilot.press("ctrl+w")
        await pilot.pause()
        assert app.focused is table


# ---------------------------------------------------------------------------
# Old non-vim bindings should no longer fire task actions
# ---------------------------------------------------------------------------


async def test_e_no_longer_opens_edit_screen(db_engine) -> None:
    with Session(db_engine) as s:
        s.add(Task(title="t"))
        s.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")  # pre-vim key; must be a no-op now
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def test_d_no_longer_opens_delete_screen(db_engine) -> None:
    with Session(db_engine) as s:
        s.add(Task(title="t"))
        s.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")  # pre-vim key; must be a no-op now
        await pilot.pause()
        assert len(app.screen_stack) == 1
