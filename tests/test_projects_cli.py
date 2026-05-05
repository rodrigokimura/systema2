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


def _last_project(session: Session) -> Project:
    projects = list(session.exec(select(Project)).all())
    assert projects, "expected at least one project in the DB"
    return projects[-1]


def _last_task(session: Session) -> Task:
    tasks = list(session.exec(select(Task)).all())
    assert tasks, "expected at least one task in the DB"
    return tasks[-1]


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


def test_project_create(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(
        cli_app, ["project", "create", "home", "-d", "chores"]
    )
    assert result.exit_code == 0, result.output
    assert "Created project" in result.output

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
    with Session(db_engine) as s:
        pid = _last_project(s).id

    result = runner.invoke(
        cli_app, ["project", "update", pid, "-n", "renamed"]
    )
    assert result.exit_code == 0, result.output
    assert f"Updated project {pid}" in result.output

    with Session(db_engine) as s:
        p = s.get(Project, pid)
    assert p is not None
    assert p.name == "renamed"


def test_project_update_partial_preserves_name(
    db_engine, runner: CliRunner
) -> None:
    runner.invoke(cli_app, ["project", "create", "keep", "-d", "old desc"])
    with Session(db_engine) as s:
        pid = _last_project(s).id
    result = runner.invoke(
        cli_app, ["project", "update", pid, "-d", "new desc"]
    )
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        p = s.get(Project, pid)
    assert p is not None
    assert p.name == "keep"
    assert p.description == "new desc"


def test_project_update_not_found(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["project", "update", "nonexistent", "-n", "x"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_project_show(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "work"])
    with Session(db_engine) as s:
        pid = _last_project(s).id
    result = runner.invoke(cli_app, ["project", "show", pid])
    assert result.exit_code == 0
    assert "work" in result.output


def test_project_show_with_tasks(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "work"])
    with Session(db_engine) as s:
        pid = _last_project(s).id
    runner.invoke(cli_app, ["create", "deep work", "-p", pid])
    runner.invoke(cli_app, ["create", "shallow"])

    result = runner.invoke(
        cli_app, ["project", "show", pid, "--with-tasks"]
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
    with Session(db_engine) as s:
        pid = _last_project(s).id
    runner.invoke(cli_app, ["create", "task A", "-p", pid])
    runner.invoke(cli_app, ["create", "task B", "-p", pid])

    result = runner.invoke(cli_app, ["project", "delete", pid, "--yes"])
    assert result.exit_code == 0, result.output
    assert f"Deleted project {pid}" in result.output

    with Session(db_engine) as s:
        assert s.get(Project, pid) is None
        tasks = list(s.exec(select(Task)).all())
        assert len(tasks) == 2
        for t in tasks:
            assert t.project_id is None


def test_project_delete_not_found(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["project", "delete", "nonexistent", "--yes"])
    assert result.exit_code == 1
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# Task commands with project option
# ---------------------------------------------------------------------------


def test_task_create_with_project(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "work"])
    with Session(db_engine) as s:
        pid = _last_project(s).id
    result = runner.invoke(cli_app, ["create", "deep work", "-p", pid])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = _last_task(s)
    assert task is not None
    assert task.project_id == pid


def test_task_create_missing_project_exits_1(
    db_engine, runner: CliRunner
) -> None:
    result = runner.invoke(cli_app, ["create", "x", "-p", "nonexistent"])
    assert result.exit_code == 1
    assert "Project nonexistent not found" in result.output


def test_task_update_change_project(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "p1"])
    runner.invoke(cli_app, ["project", "create", "p2"])
    with Session(db_engine) as s:
        p1 = _last_project(s)
        # p2 is the one before p1 in the list... actually list is ordered by id.
        projects = list(s.exec(select(Project)).all())
    assert len(projects) == 2
    p1_id, p2_id = projects[0].id, projects[1].id

    runner.invoke(cli_app, ["create", "T", "-p", p1_id])
    with Session(db_engine) as s:
        tid = _last_task(s).id

    result = runner.invoke(cli_app, ["update", tid, "-p", p2_id])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, tid)
    assert task is not None
    assert task.project_id == p2_id


def test_task_update_clear_project(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "p"])
    with Session(db_engine) as s:
        pid = _last_project(s).id
    runner.invoke(cli_app, ["create", "T", "-p", pid])
    with Session(db_engine) as s:
        tid = _last_task(s).id

    result = runner.invoke(cli_app, ["update", tid, "--clear-project"])
    assert result.exit_code == 0, result.output

    with Session(db_engine) as s:
        task = s.get(Task, tid)
    assert task is not None
    assert task.project_id is None


def test_task_update_project_and_clear_conflict(
    db_engine, runner: CliRunner
) -> None:
    runner.invoke(cli_app, ["project", "create", "p"])
    with Session(db_engine) as s:
        pid = _last_project(s).id
    runner.invoke(cli_app, ["create", "T"])
    with Session(db_engine) as s:
        tid = _last_task(s).id

    result = runner.invoke(
        cli_app, ["update", tid, "-p", pid, "--clear-project"]
    )
    assert result.exit_code == 2
    assert "not both" in result.output


def test_task_list_filter_by_project(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "p1"])
    runner.invoke(cli_app, ["project", "create", "p2"])
    with Session(db_engine) as s:
        projects = list(s.exec(select(Project)).all())
    p1_id, p2_id = projects[0].id, projects[1].id

    runner.invoke(cli_app, ["create", "alpha-task", "-p", p1_id])
    runner.invoke(cli_app, ["create", "beta-task", "-p", p2_id])
    runner.invoke(cli_app, ["create", "orphan"])

    result = runner.invoke(cli_app, ["list", "-p", p1_id])
    assert result.exit_code == 0
    # Use long, unique titles so accidental matches in nanoid IDs are
    # astronomically unlikely.
    assert "alpha-task" in result.output
    assert "beta-task" not in result.output
    assert "orphan" not in result.output


def test_task_list_unassigned(db_engine, runner: CliRunner) -> None:
    runner.invoke(cli_app, ["project", "create", "p"])
    with Session(db_engine) as s:
        pid = _last_project(s).id
    runner.invoke(cli_app, ["create", "inside", "-p", pid])
    runner.invoke(cli_app, ["create", "outside"])

    result = runner.invoke(cli_app, ["list", "--unassigned"])
    assert result.exit_code == 0
    assert "outside" in result.output
    assert "inside" not in result.output


def test_task_list_filter_conflict(db_engine, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["list", "-p", "nonexistent", "--unassigned"])
    assert result.exit_code == 2
    assert "not both" in result.output
