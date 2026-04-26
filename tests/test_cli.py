from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from typer.testing import CliRunner

from systema2 import cli as cli_module
from systema2 import database as database_module
from systema2.models import Task


@pytest.fixture
def cli_engine(monkeypatch: pytest.MonkeyPatch) -> Generator[object, None, None]:
    """Swap the module-level engine for an in-memory one for CLI tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # The CLI imports `engine` by name from systema2.database, so patch both.
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(cli_module, "engine", engine)
    # init_db() would call create_all on the real engine; make it a no-op
    # since we've already created tables on our test engine.
    monkeypatch.setattr(cli_module, "init_db", lambda: None)

    yield engine
    engine.dispose()


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_create(cli_engine, runner: CliRunner) -> None:
    result = runner.invoke(
        cli_module.app,
        ["create", "first task", "-d", "desc here"],
    )
    assert result.exit_code == 0, result.output
    assert "Created task 1" in result.output

    with Session(cli_engine) as session:
        tasks = list(session.exec(select(Task)).all())
    assert len(tasks) == 1
    assert tasks[0].title == "first task"
    assert tasks[0].description == "desc here"
    assert tasks[0].completed is False


def test_cli_create_validation_error(cli_engine, runner: CliRunner) -> None:
    # Empty title violates min_length=1 on TaskCreate
    result = runner.invoke(cli_module.app, ["create", ""])
    assert result.exit_code != 0


def test_cli_list_empty(cli_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_module.app, ["list"])
    assert result.exit_code == 0
    assert "No tasks" in result.output


def test_cli_update(cli_engine, runner: CliRunner) -> None:
    runner.invoke(cli_module.app, ["create", "original"])

    result = runner.invoke(
        cli_module.app,
        ["update", "1", "-t", "renamed", "--completed"],
    )
    assert result.exit_code == 0, result.output
    assert "Updated task 1" in result.output

    with Session(cli_engine) as session:
        task = session.get(Task, 1)
    assert task is not None
    assert task.title == "renamed"
    assert task.completed is True


def test_cli_update_partial_preserves_title(
    cli_engine, runner: CliRunner
) -> None:
    """Regression: updating only --completed must not null out title."""
    runner.invoke(cli_module.app, ["create", "keep me", "-d", "keep desc"])

    result = runner.invoke(cli_module.app, ["update", "1", "--completed"])
    assert result.exit_code == 0, result.output

    with Session(cli_engine) as session:
        task = session.get(Task, 1)
    assert task is not None
    assert task.title == "keep me"
    assert task.description == "keep desc"
    assert task.completed is True


def test_cli_update_not_found(cli_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_module.app, ["update", "999", "-t", "x"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_cli_delete(cli_engine, runner: CliRunner) -> None:
    runner.invoke(cli_module.app, ["create", "doomed"])

    result = runner.invoke(cli_module.app, ["delete", "1", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Deleted task 1" in result.output

    with Session(cli_engine) as session:
        assert session.get(Task, 1) is None


def test_cli_delete_not_found(cli_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_module.app, ["delete", "999", "--yes"])
    assert result.exit_code == 1
    assert "not found" in result.output
