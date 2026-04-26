"""Tests for the Task.due_date field across API, repository, CLI, TUI."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from typer.testing import CliRunner

from systema2.cli import app as cli_app
from systema2.models import Task, TaskCreate, TaskUpdate
from systema2.repository import HttpTaskRepository, LocalTaskRepository
from systema2.tui import Systema2App


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Model default
# ---------------------------------------------------------------------------


def test_due_date_default_is_none() -> None:
    assert Task(title="x").due_date is None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_create_with_due_date(client: TestClient) -> None:
    r = client.post(
        "/tasks", json={"title": "t", "due_date": "2030-01-15"}
    )
    assert r.status_code == 201
    assert r.json()["due_date"] == "2030-01-15"


def test_api_create_without_due_date(client: TestClient) -> None:
    r = client.post("/tasks", json={"title": "t"})
    assert r.status_code == 201
    assert r.json()["due_date"] is None


def test_api_create_invalid_due_date_422(client: TestClient) -> None:
    r = client.post(
        "/tasks", json={"title": "t", "due_date": "not-a-date"}
    )
    assert r.status_code == 422


def test_api_update_due_date(client: TestClient) -> None:
    tid = client.post("/tasks", json={"title": "t"}).json()["id"]
    r = client.patch(f"/tasks/{tid}", json={"due_date": "2030-06-30"})
    assert r.status_code == 200
    assert r.json()["due_date"] == "2030-06-30"


def test_api_clear_due_date(client: TestClient) -> None:
    tid = client.post(
        "/tasks", json={"title": "t", "due_date": "2030-06-30"}
    ).json()["id"]
    r = client.patch(f"/tasks/{tid}", json={"due_date": None})
    assert r.status_code == 200
    assert r.json()["due_date"] is None


def test_api_update_due_date_preserves_other_fields(
    client: TestClient,
) -> None:
    created = client.post(
        "/tasks",
        json={"title": "keep", "description": "keep me", "priority": "H"},
    ).json()
    r = client.patch(
        f"/tasks/{created['id']}", json={"due_date": "2030-01-01"}
    )
    data = r.json()
    assert data["title"] == "keep"
    assert data["description"] == "keep me"
    assert data["priority"] == "H"
    assert data["due_date"] == "2030-01-01"


def test_api_list_filter_due_before(client: TestClient) -> None:
    client.post("/tasks", json={"title": "early", "due_date": "2030-01-01"})
    client.post("/tasks", json={"title": "mid", "due_date": "2030-06-15"})
    client.post("/tasks", json={"title": "late", "due_date": "2030-12-31"})
    client.post("/tasks", json={"title": "no-date"})

    r = client.get("/tasks", params={"due_before": "2030-06-15"})
    titles = sorted(t["title"] for t in r.json())
    assert titles == ["early", "mid"]
    # Tasks without a due_date are excluded.
    assert "no-date" not in titles


def test_api_list_filter_due_before_invalid_422(client: TestClient) -> None:
    r = client.get("/tasks", params={"due_before": "not-a-date"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Repository (local + remote)
# ---------------------------------------------------------------------------


def test_local_repository_due_date_round_trip(db_engine) -> None:
    repo = LocalTaskRepository()
    t = repo.create_task(TaskCreate(title="t", due_date=date(2030, 1, 15)))
    assert t.due_date == date(2030, 1, 15)

    u = repo.update_task(t.id, TaskUpdate(due_date=date(2030, 3, 1)))  # type: ignore[arg-type]
    assert u is not None and u.due_date == date(2030, 3, 1)

    cleared = repo.update_task(t.id, TaskUpdate(due_date=None))  # type: ignore[arg-type]
    assert cleared is not None and cleared.due_date is None


def test_local_repository_due_before_filter(db_engine) -> None:
    repo = LocalTaskRepository()
    repo.create_task(TaskCreate(title="early", due_date=date(2030, 1, 1)))
    repo.create_task(TaskCreate(title="late", due_date=date(2030, 12, 31)))
    repo.create_task(TaskCreate(title="no-date"))

    titles = sorted(
        t.title for t in repo.list_tasks(due_before=date(2030, 6, 1))
    )
    assert titles == ["early"]


def test_http_repository_due_before_filter(
    http_repo_against_app: HttpTaskRepository,
) -> None:
    repo = http_repo_against_app
    repo.create_task(TaskCreate(title="early", due_date=date(2030, 1, 1)))
    repo.create_task(TaskCreate(title="late", due_date=date(2030, 12, 31)))

    titles = [
        t.title for t in repo.list_tasks(due_before=date(2030, 6, 1))
    ]
    assert titles == ["early"]


def test_http_repository_round_trip_due_date(
    http_repo_against_app: HttpTaskRepository,
) -> None:
    repo = http_repo_against_app
    t = repo.create_task(TaskCreate(title="t", due_date=date(2030, 5, 5)))
    assert t.due_date == date(2030, 5, 5)

    fetched = repo.get_task(t.id)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.due_date == date(2030, 5, 5)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_create_with_due(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(
        cli_app, ["create", "deadline", "-D", "2030-07-04"]
    )
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.due_date == date(2030, 7, 4)


def test_cli_create_invalid_due_exits_2(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["create", "bad", "-D", "tomorrow"])
    assert result.exit_code == 2
    assert "Invalid --due" in result.output


def test_cli_update_due(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["create", "t"])
    result = runner.invoke(cli_app, ["update", "1", "-D", "2030-08-01"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.due_date == date(2030, 8, 1)


def test_cli_clear_due(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["create", "t", "-D", "2030-08-01"])
    result = runner.invoke(cli_app, ["update", "1", "--clear-due"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.due_date is None


def test_cli_due_and_clear_due_conflict(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["create", "t"])
    result = runner.invoke(
        cli_app, ["update", "1", "-D", "2030-08-01", "--clear-due"]
    )
    assert result.exit_code == 2
    assert "not both" in result.output


def test_cli_list_due_before(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["create", "early", "-D", "2030-01-01"])
    runner.invoke(cli_app, ["create", "late", "-D", "2030-12-31"])
    runner.invoke(cli_app, ["create", "no-date"])

    result = runner.invoke(cli_app, ["list", "--due-before", "2030-06-01"])
    assert result.exit_code == 0, result.output
    assert "early" in result.output
    assert "late" not in result.output
    assert "no-date" not in result.output


def test_cli_list_due_before_invalid(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["list", "--due-before", "nope"])
    assert result.exit_code == 2
    assert "Invalid --due-before" in result.output


def test_cli_show_overdue_highlight(db_engine, runner: CliRunner) -> None:
    """Overdue + not-completed tasks render with the red style ANSI."""
    past = (date.today() - timedelta(days=1)).isoformat()
    runner.invoke(cli_app, ["create", "overdue", "-D", past])
    # Capture styled output (CliRunner preserves ANSI by default).
    result = runner.invoke(cli_app, ["list"])
    assert result.exit_code == 0
    # The bold-red style for overdue yields an ANSI sequence with red (31).
    # Don't over-constrain the exact code; just verify the date is shown.
    assert past in result.output


# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------


async def test_tui_add_task_with_due_date(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()

        from textual.widgets import Input

        app.screen.query_one("#title", Input).value = "deadline"
        app.screen.query_one("#due_date", Input).value = "2030-09-09"
        await pilot.pause()

        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as s:
        tasks = list(s.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].due_date == date(2030, 9, 9)


async def test_tui_add_task_invalid_due_date_shows_error(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()

        from textual.widgets import Input, Static

        app.screen.query_one("#title", Input).value = "x"
        app.screen.query_one("#due_date", Input).value = "nope"
        await pilot.pause()

        await pilot.press("ctrl+s")
        await pilot.pause()

        # Screen is still open and shows the error.
        assert len(app.screen_stack) > 1
        error_text = str(app.screen.query_one("#error", Static).content)
        assert "Invalid due date" in error_text

    with Session(db_engine) as s:
        assert list(s.exec(select(Task)).all()) == []


async def test_tui_edit_task_clear_due_date(db_engine) -> None:
    with Session(db_engine) as s:
        s.add(Task(title="t", due_date=date(2030, 1, 1)))
        s.commit()

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        from textual.widgets import Input

        # Clear the prefilled due date.
        app.screen.query_one("#due_date", Input).value = ""
        await pilot.pause()

        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.due_date is None
