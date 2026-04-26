"""CLI tests for project commands and task/project integration."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select
from typer.testing import CliRunner

from systema2.cli import app as cli_app
from systema2.models import Project, Task


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


def test_project_create(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(
        cli_app, ["project", "create", "home", "-d", "chores"]
    )
    assert result.exit_code == 0, result.output
    assert "Created project 1" in result.output

    with Session(db_engine) as s:
        projects = list(s.exec(select(Project)).all())
    assert len(projects) == 1
    assert projects[0].name == "home"
    assert projects[0].description == "chores"


def test_project_list_empty(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["project", "list"])
    assert result.exit_code == 0
    assert "No projects" in result.output


def test_project_update(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "old"])

    result = runner.invoke(
        cli_app, ["project", "update", "1", "-n", "renamed"]
    )
    assert result.exit_code == 0, result.output
    assert "Updated project 1" in result.output

    with Session(db_engine) as s:
        p = s.get(Project, 1)
    assert p is not None
    assert p.name == "renamed"


def test_project_update_partial_preserves_name(
    db_engine, runner: CliRunner
) -> None:
    runner.invoke(
        cli_app, ["project", "create", "keep", "-d", "old desc"]
    )
    result = runner.invoke(
        cli_app, ["project", "update", "1", "-d", "new desc"]
    )
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        p = s.get(Project, 1)
    assert p is not None
    assert p.name == "keep"
    assert p.description == "new desc"


def test_project_update_not_found(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["project", "update", "999", "-n", "x"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_project_show(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "work"])
    result = runner.invoke(cli_app, ["project", "show", "1"])
    assert result.exit_code == 0
    assert "work" in result.output


def test_project_show_with_tasks(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "work"])
    runner.invoke(cli_app, ["create", "deep work", "-p", "1"])
    runner.invoke(cli_app, ["create", "shallow"])

    result = runner.invoke(
        cli_app, ["project", "show", "1", "--with-tasks"]
    )
    assert result.exit_code == 0, result.output
    assert "work" in result.output
    assert "deep work" in result.output
    # Task not in project should not appear.
    assert "shallow" not in result.output


def test_project_delete_unlinks_tasks(
    db_engine, runner: CliRunner
) -> None:
    runner.invoke(cli_app, ["project", "create", "doomed"])
    runner.invoke(cli_app, ["create", "task A", "-p", "1"])
    runner.invoke(cli_app, ["create", "task B", "-p", "1"])

    result = runner.invoke(cli_app, ["project", "delete", "1", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Deleted project 1" in result.output

    with Session(db_engine) as s:
        assert s.get(Project, 1) is None
        tasks = list(s.exec(select(Task)).all())
        assert len(tasks) == 2
        for t in tasks:
            assert t.project_id is None


def test_project_delete_not_found(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["project", "delete", "999", "--yes"])
    assert result.exit_code == 1
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# Task commands with project option
# ---------------------------------------------------------------------------


def test_task_create_with_project(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "work"])
    result = runner.invoke(cli_app, ["create", "deep work", "-p", "1"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.project_id == 1


def test_task_create_missing_project_exits_1(
    db_engine, runner: CliRunner
) -> None:
    result = runner.invoke(cli_app, ["create", "x", "-p", "999"])
    assert result.exit_code == 1
    assert "Project 999 not found" in result.output


def test_task_update_change_project(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "p1"])
    runner.invoke(cli_app, ["project", "create", "p2"])
    runner.invoke(cli_app, ["create", "T", "-p", "1"])

    result = runner.invoke(cli_app, ["update", "1", "-p", "2"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.project_id == 2


def test_task_update_clear_project(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "p"])
    runner.invoke(cli_app, ["create", "T", "-p", "1"])

    result = runner.invoke(cli_app, ["update", "1", "--clear-project"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, 1)
    assert task is not None
    assert task.project_id is None


def test_task_update_project_and_clear_conflict(
    db_engine, runner: CliRunner
) -> None:
    runner.invoke(cli_app, ["project", "create", "p"])
    runner.invoke(cli_app, ["create", "T"])

    result = runner.invoke(
        cli_app, ["update", "1", "-p", "1", "--clear-project"]
    )
    assert result.exit_code == 2
    assert "not both" in result.output


def test_task_list_filter_by_project(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "p1"])
    runner.invoke(cli_app, ["project", "create", "p2"])
    runner.invoke(cli_app, ["create", "a", "-p", "1"])
    runner.invoke(cli_app, ["create", "b", "-p", "2"])
    runner.invoke(cli_app, ["create", "orphan"])

    result = runner.invoke(cli_app, ["list", "-p", "1"])
    assert result.exit_code == 0
    assert "a" in result.output
    assert "b" not in result.output
    assert "orphan" not in result.output


def test_task_list_unassigned(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "p"])
    runner.invoke(cli_app, ["create", "inside", "-p", "1"])
    runner.invoke(cli_app, ["create", "outside"])

    result = runner.invoke(cli_app, ["list", "--unassigned"])
    assert result.exit_code == 0
    assert "outside" in result.output
    assert "inside" not in result.output


def test_task_list_filter_conflict(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["list", "-p", "1", "--unassigned"])
    assert result.exit_code == 2
    assert "not both" in result.output
