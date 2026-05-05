from __future__ import annotations

import pytest
from sqlmodel import Session, select
from typer.testing import CliRunner

from systema2.cli import app as cli_app
from systema2.models import Task
from systema2.repository import get_repository


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_create(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["create", "first task", "-d", "desc here"])
    assert result.exit_code == 0, result.output
    assert "Created task" in result.output

    with Session(db_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].title == "first task"
    assert tasks[0].description == "desc here"
    assert tasks[0].completed is False


def test_cli_create_validation_error(db_engine, runner: CliRunner) -> None:
    # Empty title violates min_length=1 on TaskCreate
    result = runner.invoke(cli_app, ["create", ""])
    assert result.exit_code != 0


def test_cli_list_empty(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["list"])
    assert result.exit_code == 0
    assert "No tasks" in result.output


def test_cli_update(db_engine, runner: CliRunner) -> None:
    repo = get_repository()
    task = repo.create_task(Task(title="original"))

    result = runner.invoke(
        cli_app, ["update", task.id, "-t", "renamed", "--completed"]
    )
    assert result.exit_code == 0, result.output
    assert f"Updated task {task.id}" in result.output

    with Session(db_engine) as session:
        fresh = session.get(Task, task.id)
    assert fresh is not None
    assert fresh.title == "renamed"
    assert fresh.completed is True


def test_cli_update_partial_preserves_title(
    db_engine, runner: CliRunner
) -> None:
    """Regression: updating only --completed must not null out title."""
    repo = get_repository()
    task = repo.create_task(Task(title="keep me", description="keep desc"))

    result = runner.invoke(cli_app, ["update", task.id, "--completed"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as session:
        fresh = session.get(Task, task.id)
    assert fresh is not None
    assert fresh.title == "keep me"
    assert fresh.description == "keep desc"
    assert fresh.completed is True


def test_cli_update_not_found(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(
        cli_app, ["update", "nonexistent", "-t", "x"]
    )
    assert result.exit_code == 1
    assert "not found" in result.output


def test_cli_delete(db_engine, runner: CliRunner) -> None:
    repo = get_repository()
    task = repo.create_task(Task(title="doomed"))

    result = runner.invoke(cli_app, ["delete", task.id, "--yes"])
    assert result.exit_code == 0, result.output
    assert f"Deleted task {task.id}" in result.output

    with Session(db_engine) as session:
        assert session.get(Task, task.id) is None


def test_cli_delete_not_found(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["delete", "nonexistent", "--yes"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_cli_tui_invokes_app(
    db_engine, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`systema2 tui` should instantiate Systema2App and call .run()."""
    calls: list[str] = []

    class FakeApp:
        def run(self) -> None:
            calls.append("run")

    # Patch where the CLI's lazy import looks up the class.
    from systema2 import tui as tui_module

    monkeypatch.setattr(tui_module, "Systema2App", FakeApp)

    result = runner.invoke(cli_app, ["tui"])
    assert result.exit_code == 0, result.output
    assert calls == ["run"]


def test_cli_serve_invokes_uvicorn(
    db_engine, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`systema2 serve` should call uvicorn.run with the configured host/port."""
    captured: dict[str, object] = {}

    import uvicorn

    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)

    result = runner.invoke(
        cli_app, ["serve", "--host", "0.0.0.0", "--port", "9123"]
    )
    assert result.exit_code == 0, result.output
    assert captured["app"] == "systema2.app:app"
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9123
    assert captured["reload"] is False
