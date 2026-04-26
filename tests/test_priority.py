"""Tests for the Task.priority field across API, repository, CLI, TUI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from typer.testing import CliRunner

from systema2.cli import app as cli_app
from systema2.models import Priority, Task, TaskCreate, TaskUpdate
from systema2.repository import HttpTaskRepository, LocalTaskRepository
from systema2.tui import Systema2App


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


def test_priority_default_is_medium() -> None:
    t = Task(title="x")
    assert t.priority is Priority.MEDIUM


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_create_default_priority(client: TestClient) -> None:
    r = client.post("/tasks", json={"title": "default pri"})
    assert r.status_code == 201
    assert r.json()["priority"] == "M"


def test_api_create_with_priority(client: TestClient) -> None:
    r = client.post(
        "/tasks", json={"title": "urgent", "priority": "H"}
    )
    assert r.status_code == 201
    assert r.json()["priority"] == "H"


def test_api_create_invalid_priority_422(client: TestClient) -> None:
    r = client.post(
        "/tasks", json={"title": "bad", "priority": "URGENT"}
    )
    assert r.status_code == 422


def test_api_update_priority(client: TestClient) -> None:
    tid = client.post("/tasks", json={"title": "t"}).json()["id"]
    r = client.patch(f"/tasks/{tid}", json={"priority": "L"})
    assert r.status_code == 200
    assert r.json()["priority"] == "L"


def test_api_update_priority_preserves_other_fields(
    client: TestClient,
) -> None:
    created = client.post(
        "/tasks",
        json={"title": "keep", "description": "keep me", "priority": "H"},
    ).json()
    r = client.patch(f"/tasks/{created['id']}", json={"priority": "L"})
    data = r.json()
    assert data["title"] == "keep"
    assert data["description"] == "keep me"
    assert data["priority"] == "L"


def test_api_list_filter_by_priority(client: TestClient) -> None:
    client.post("/tasks", json={"title": "h1", "priority": "H"})
    client.post("/tasks", json={"title": "h2", "priority": "H"})
    client.post("/tasks", json={"title": "m", "priority": "M"})
    client.post("/tasks", json={"title": "l", "priority": "L"})

    for p, expected in [("H", {"h1", "h2"}), ("M", {"m"}), ("L", {"l"})]:
        r = client.get("/tasks", params={"priority": p})
        assert r.status_code == 200
        titles = {t["title"] for t in r.json()}
        assert titles == expected


def test_api_list_filter_invalid_priority_422(client: TestClient) -> None:
    r = client.get("/tasks", params={"priority": "X"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Repository (local + remote)
# ---------------------------------------------------------------------------


def test_local_repository_priority_round_trip(db_engine) -> None:
    repo = LocalTaskRepository()
    t = repo.create_task(TaskCreate(title="t", priority=Priority.HIGH))
    assert t.priority is Priority.HIGH

    u = repo.update_task(t.id, TaskUpdate(priority=Priority.LOW))  # type: ignore[arg-type]
    assert u is not None and u.priority is Priority.LOW


def test_local_repository_priority_filter(db_engine) -> None:
    repo = LocalTaskRepository()
    repo.create_task(TaskCreate(title="h", priority=Priority.HIGH))
    repo.create_task(TaskCreate(title="m"))  # default Medium
    repo.create_task(TaskCreate(title="l", priority=Priority.LOW))

    assert [t.title for t in repo.list_tasks(priority=Priority.HIGH)] == ["h"]
    assert [t.title for t in repo.list_tasks(priority=Priority.LOW)] == ["l"]


def test_http_repository_priority_filter(
    http_repo_against_app: HttpTaskRepository,
) -> None:
    repo = http_repo_against_app
    repo.create_task(TaskCreate(title="h", priority=Priority.HIGH))
    repo.create_task(TaskCreate(title="m", priority=Priority.MEDIUM))

    highs = [t.title for t in repo.list_tasks(priority=Priority.HIGH)]
    assert highs == ["h"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_create_with_priority(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["create", "urgent", "-P", "H"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.priority is Priority.HIGH


def test_cli_create_default_priority_medium(
    db_engine, runner: CliRunner
) -> None:
    result = runner.invoke(cli_app, ["create", "plain"])
    assert result.exit_code == 0

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.priority is Priority.MEDIUM


def test_cli_create_invalid_priority(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["create", "bad", "-P", "X"])
    assert result.exit_code != 0
    assert "H" in result.output and "M" in result.output and "L" in result.output


def test_cli_update_priority(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["create", "t"])
    result = runner.invoke(cli_app, ["update", "1", "-P", "L"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.priority is Priority.LOW


def test_cli_list_filter_by_priority(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["create", "h-task", "-P", "H"])
    runner.invoke(cli_app, ["create", "m-task"])
    runner.invoke(cli_app, ["create", "l-task", "-P", "L"])

    result = runner.invoke(cli_app, ["list", "-P", "H"])
    assert result.exit_code == 0
    assert "h-task" in result.output
    assert "m-task" not in result.output
    assert "l-task" not in result.output


# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------


async def test_tui_add_task_defaults_to_medium(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        for ch in "plain":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as s:
        tasks = list(s.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].priority is Priority.MEDIUM


async def test_tui_edit_task_priority_via_select(db_engine) -> None:
    """Simulate editing a task and changing its priority via the Select widget.

    We don't navigate keyboard focus through the dropdown (Textual's Select
    UX is fiddly to drive via Pilot). Instead we open the EditTaskScreen
    and assign the select value programmatically, then submit.
    """
    with Session(db_engine) as s:
        s.add(Task(title="t", priority=Priority.MEDIUM))
        s.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        from textual.widgets import Select

        select = app.screen.query_one("#priority", Select)
        select.value = Priority.HIGH.value
        await pilot.pause()

        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.priority is Priority.HIGH
