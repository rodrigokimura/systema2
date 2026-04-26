from __future__ import annotations

import pytest
from sqlmodel import Session, select
from typer.testing import CliRunner

from systema2.cli import app as cli_app
from systema2.models import Task


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_create(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["create", "first task", "-d", "desc here"])
    assert result.exit_code == 0, result.output
    assert "Created task 1" in result.output

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
    runner.invoke(cli_app, ["create", "original"])

    result = runner.invoke(cli_app, ["update", "1", "-t", "renamed", "--completed"])
    assert result.exit_code == 0, result.output
    assert "Updated task 1" in result.output

    with Session(db_engine) as session:
        task = session.get(Task, 1)
    assert task is not None
    assert task.title == "renamed"
    assert task.completed is True


def test_cli_update_partial_preserves_title(db_engine, runner: CliRunner) -> None:
    """Regression: updating only --completed must not null out title."""
    runner.invoke(cli_app, ["create", "keep me", "-d", "keep desc"])

    result = runner.invoke(cli_app, ["update", "1", "--completed"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as session:
        task = session.get(Task, 1)
    assert task is not None
    assert task.title == "keep me"
    assert task.description == "keep desc"
    assert task.completed is True


def test_cli_update_not_found(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["update", "999", "-t", "x"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_cli_delete(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["create", "doomed"])

    result = runner.invoke(cli_app, ["delete", "1", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Deleted task 1" in result.output

    with Session(db_engine) as session:
        assert session.get(Task, 1) is None


def test_cli_delete_not_found(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["delete", "999", "--yes"])
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
