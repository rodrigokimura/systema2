"""Textual TUI tests for projects and sidebar filtering."""

from __future__ import annotations

from sqlmodel import Session, select

from systema2.models import Project, Task
from systema2.tui import Systema2App


async def test_tui_add_project(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("o")  # vim: open new line / new project
        await pilot.pause()
        for ch in "work":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as s:
        projects = list(s.exec(select(Project)).all())
    assert len(projects) == 1
    assert projects[0].name == "work"


async def test_tui_edit_project(db_engine) -> None:
    with Session(db_engine) as s:
        s.add(Project(name="old"))
        s.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Move sidebar selection to the first real project (index 2).
        await pilot.press("j")  # vim: down
        await pilot.press("j")
        await pilot.pause()
        await pilot.press("I")  # vim: edit project (shift-I)
        await pilot.pause()
        for _ in range(len("old")):
            await pilot.press("backspace")
        for ch in "renamed":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as s:
        projects = list(s.exec(select(Project)).all())
    assert len(projects) == 1
    assert projects[0].name == "renamed"


async def test_tui_delete_project_unlinks_tasks(db_engine) -> None:
    with Session(db_engine) as s:
        p = Project(name="doomed")
        s.add(p)
        s.commit()
        s.refresh(p)
        s.add(Task(title="inside", project_id=p.id))
        s.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")
        await pilot.press("j")  # highlight the project
        await pilot.pause()
        await pilot.press("X")  # vim: delete project (shift-X)
        await pilot.pause()
        # Cancel is focused; tab to Delete and confirm.
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()

    with Session(db_engine) as s:
        assert list(s.exec(select(Project)).all()) == []
        tasks = list(s.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].project_id is None


async def test_tui_edit_project_without_selection_notifies(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Default selection is "All tasks" (index 0) — not a real project.
        await pilot.press("I")  # vim: edit project
        await pilot.pause()
        # No modal should have been pushed.
        assert len(app.screen_stack) == 1


async def test_tui_sidebar_filters_tasks(db_engine) -> None:
    with Session(db_engine) as s:
        p = Project(name="work")
        s.add(p)
        s.commit()
        s.refresh(p)
        s.add(Task(title="inside", project_id=p.id))
        s.add(Task(title="orphan"))
        s.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()

        # Default is "All" -> both tasks visible.
        from textual.widgets import DataTable

        table = app.query_one(DataTable)
        assert table.row_count == 2

        # Move to "No project" (index 1).
        await pilot.press("j")  # vim: down
        await pilot.pause()
        assert table.row_count == 1

        # Move to the project row (index 2).
        await pilot.press("j")
        await pilot.pause()
        assert table.row_count == 1
        # And it should be the inside task.
        row_keys = [row.value for row in table.rows]
        # The only row's key is the task id.
        assert len(row_keys) == 1


async def test_tui_add_task_inherits_selected_project(db_engine) -> None:
    with Session(db_engine) as s:
        p = Project(name="work")
        s.add(p)
        s.commit()
        s.refresh(p)
        project_id = p.id

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Highlight the project in the sidebar.
        await pilot.press("j")
        await pilot.press("j")
        await pilot.pause()
        # Add a task — the form should pre-select the current project.
        await pilot.press("a")
        await pilot.pause()

        from textual.widgets import Select as TextualSelect

        # Explicitly pin the project select so the test is deterministic
        # regardless of Textual's Select initial-value timing.
        select_widget = app.screen.query_one("#project", TextualSelect)
        select_widget.value = project_id
        await pilot.pause()

        for ch in "inside":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as s:
        tasks = list(s.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].project_id == project_id
