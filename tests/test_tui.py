"""End-to-end tests for the Textual TUI using the Pilot harness."""

from __future__ import annotations

from sqlmodel import Session, select

from systema2.models import Task
from systema2.tui import Systema2App


async def test_tui_add_task(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.press("a")  # open AddTaskScreen
        await pilot.pause()
        for ch in "hello":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].title == "hello"
    assert tasks[0].completed is False


async def test_tui_add_task_cancel_with_escape(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        for ch in "nope":
            await pilot.press(ch)
        await pilot.press("escape")
        await pilot.pause()

    with Session(db_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert tasks == []


async def test_tui_edit_task(db_engine) -> None:
    with Session(db_engine) as session:
        session.add(Task(title="original"))
        session.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        # #title input is focused and populated with "original".
        for _ in range(len("original")):
            await pilot.press("backspace")
        for ch in "renamed":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].title == "renamed"


async def test_tui_edit_without_selection_notifies(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.press("e")  # no rows -> warning, no screen pushed
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def test_tui_delete_task(db_engine) -> None:
    with Session(db_engine) as session:
        session.add(Task(title="doomed"))
        session.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        # DeleteTaskScreen focuses #cancel; tab to Delete and press enter.
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()

    with Session(db_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert tasks == []


async def test_tui_delete_cancelled(db_engine) -> None:
    with Session(db_engine) as session:
        session.add(Task(title="keep me"))
        session.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    with Session(db_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].title == "keep me"
