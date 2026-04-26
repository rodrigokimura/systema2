"""End-to-end tests for the Textual TUI using the Pilot harness."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from systema2 import database as database_module
from systema2 import tui as tui_module
from systema2.models import Task
from systema2.tui import Systema2App


@pytest.fixture
def tui_engine(monkeypatch: pytest.MonkeyPatch) -> Generator[object, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(tui_module, "engine", engine)
    monkeypatch.setattr(tui_module, "init_db", lambda: None)

    yield engine
    engine.dispose()


@pytest.mark.asyncio
async def test_tui_add_task(tui_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.press("a")  # open AddTaskScreen
        await pilot.pause()
        # Type the title (focus lands on #title)
        for ch in "hello":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(tui_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].title == "hello"
    assert tasks[0].completed is False


@pytest.mark.asyncio
async def test_tui_add_task_cancel_with_escape(tui_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        for ch in "nope":
            await pilot.press(ch)
        await pilot.press("escape")
        await pilot.pause()

    with Session(tui_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert tasks == []


@pytest.mark.asyncio
async def test_tui_edit_task(tui_engine) -> None:
    # Seed a task directly.
    with Session(tui_engine) as session:
        session.add(Task(title="original"))
        session.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")  # open EditTaskScreen for the only row
        await pilot.pause()
        # #title input is focused and populated with "original".
        # Clear it (8 chars) then type a new title.
        for _ in range(len("original")):
            await pilot.press("backspace")
        for ch in "renamed":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(tui_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].title == "renamed"


@pytest.mark.asyncio
async def test_tui_edit_without_selection_notifies(tui_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.press("e")  # no rows -> warning, no screen pushed
        await pilot.pause()
        # Still only the default screen on the stack.
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_tui_delete_task(tui_engine) -> None:
    with Session(tui_engine) as session:
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

    with Session(tui_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert tasks == []


@pytest.mark.asyncio
async def test_tui_delete_cancelled(tui_engine) -> None:
    with Session(tui_engine) as session:
        session.add(Task(title="keep me"))
        session.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    with Session(tui_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].title == "keep me"
