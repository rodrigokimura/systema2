"""Tests for the repository layer and mode selection."""

from __future__ import annotations

import pytest

from systema2 import repository as repo_module
from systema2.config import Mode, get_mode
from systema2.models import ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate
from systema2.repository import (
    HttpTaskRepository,
    LocalTaskRepository,
    ProjectNotFoundError,
    RepositoryError,
    get_repository,
)


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------


def test_default_mode_is_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYSTEMA2_MODE", raising=False)
    assert get_mode() is Mode.LOCAL


@pytest.mark.parametrize(
    "value,expected",
    [
        ("local", Mode.LOCAL),
        ("LOCAL", Mode.LOCAL),
        ("client", Mode.CLIENT),
        ("server", Mode.SERVER),
    ],
)
def test_mode_from_env(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: Mode
) -> None:
    monkeypatch.setenv("SYSTEMA2_MODE", value)
    assert get_mode() is expected


def test_invalid_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMA2_MODE", "bogus")
    with pytest.raises(ValueError, match="Invalid SYSTEMA2_MODE"):
        get_mode()


def test_get_repository_local(
    monkeypatch: pytest.MonkeyPatch, db_engine
) -> None:
    monkeypatch.setenv("SYSTEMA2_MODE", "local")
    assert isinstance(get_repository(), LocalTaskRepository)


def test_get_repository_server_uses_local(
    monkeypatch: pytest.MonkeyPatch, db_engine
) -> None:
    monkeypatch.setenv("SYSTEMA2_MODE", "server")
    assert isinstance(get_repository(), LocalTaskRepository)


def test_get_repository_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMA2_MODE", "client")
    monkeypatch.setenv("SYSTEMA2_API_URL", "http://example.test:9999")
    repo = get_repository()
    assert isinstance(repo, HttpTaskRepository)
    assert repo._base_url == "http://example.test:9999"


# ---------------------------------------------------------------------------
# LocalTaskRepository (round-trips through the service layer + in-memory DB)
# ---------------------------------------------------------------------------


def test_local_repository_crud(db_engine) -> None:
    repo = LocalTaskRepository()

    assert repo.list_tasks() == []

    created = repo.create_task(
        TaskCreate(title="write docs", description="cover modes")
    )
    assert created.id is not None
    assert created.title == "write docs"

    assert len(repo.list_tasks()) == 1

    fetched = repo.get_task(created.id)
    assert fetched is not None
    assert fetched.title == "write docs"

    updated = repo.update_task(
        created.id, TaskUpdate(title="write docs v2", completed=True)
    )
    assert updated is not None
    assert updated.title == "write docs v2"
    assert updated.completed is True

    assert repo.delete_task(created.id) is True
    assert repo.get_task(created.id) is None
    assert repo.delete_task(created.id) is False


# ---------------------------------------------------------------------------
# HttpTaskRepository against the in-process FastAPI app via httpx.MockTransport
# ---------------------------------------------------------------------------


def test_http_repository_crud(http_repo_against_app: HttpTaskRepository) -> None:
    repo = http_repo_against_app

    assert repo.list_tasks() == []

    created = repo.create_task(TaskCreate(title="remote task"))
    assert created.id is not None
    assert created.title == "remote task"

    fetched = repo.get_task(created.id)
    assert fetched is not None
    assert fetched.title == "remote task"

    assert repo.get_task(9999) is None

    updated = repo.update_task(
        created.id, TaskUpdate(completed=True)
    )
    assert updated is not None
    assert updated.completed is True
    # Partial update must not null out title.
    assert updated.title == "remote task"

    missing = repo.update_task(9999, TaskUpdate(title="nope"))
    assert missing is None

    assert repo.delete_task(created.id) is True
    assert repo.delete_task(created.id) is False


# ---------------------------------------------------------------------------
# Projects (both backends)
# ---------------------------------------------------------------------------


def test_local_repository_projects_crud(db_engine) -> None:
    repo = LocalTaskRepository()
    assert repo.list_projects() == []

    p = repo.create_project(ProjectCreate(name="work", description="desk"))
    assert p.id is not None
    assert repo.get_project(p.id) is not None

    u = repo.update_project(p.id, ProjectUpdate(name="work!"))
    assert u is not None and u.name == "work!"

    assert repo.delete_project(p.id) is True
    assert repo.get_project(p.id) is None
    assert repo.delete_project(p.id) is False


def test_local_repository_task_missing_project_raises(db_engine) -> None:
    repo = LocalTaskRepository()
    with pytest.raises(ProjectNotFoundError) as exc:
        repo.create_task(TaskCreate(title="x", project_id=999))
    assert exc.value.project_id == 999


def test_http_repository_projects_crud(
    http_repo_against_app: HttpTaskRepository,
) -> None:
    repo = http_repo_against_app
    assert repo.list_projects() == []

    p = repo.create_project(ProjectCreate(name="remote"))
    assert p.id is not None
    assert repo.get_project(p.id) is not None

    u = repo.update_project(p.id, ProjectUpdate(description="new"))
    assert u is not None and u.description == "new"
    assert u.name == "remote"  # partial update must not null out name

    assert repo.delete_project(p.id) is True
    assert repo.delete_project(p.id) is False


def test_http_repository_task_missing_project_raises(
    http_repo_against_app: HttpTaskRepository,
) -> None:
    repo = http_repo_against_app
    with pytest.raises(ProjectNotFoundError) as exc:
        repo.create_task(TaskCreate(title="x", project_id=999))
    assert exc.value.project_id == 999

    p = repo.create_project(ProjectCreate(name="p"))
    t = repo.create_task(TaskCreate(title="t", project_id=p.id))
    assert t.project_id == p.id

    # Update to bogus project also raises.
    with pytest.raises(ProjectNotFoundError):
        repo.update_task(t.id, TaskUpdate(project_id=9999))  # type: ignore[arg-type]


def test_http_repository_list_tasks_filters(
    http_repo_against_app: HttpTaskRepository,
) -> None:
    repo = http_repo_against_app
    p1 = repo.create_project(ProjectCreate(name="p1"))
    p2 = repo.create_project(ProjectCreate(name="p2"))
    repo.create_task(TaskCreate(title="a", project_id=p1.id))
    repo.create_task(TaskCreate(title="b", project_id=p2.id))
    repo.create_task(TaskCreate(title="orphan"))

    titles_p1 = sorted(t.title for t in repo.list_tasks(project_id=p1.id))
    assert titles_p1 == ["a"]

    titles_unassigned = sorted(t.title for t in repo.list_tasks(unassigned=True))
    assert titles_unassigned == ["orphan"]


# ---------------------------------------------------------------------------


def test_http_repository_network_error_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreachable server -> RepositoryError (not a raw httpx exception)."""
    # Point at a closed port on localhost.
    repo = HttpTaskRepository(base_url="http://127.0.0.1:1", timeout=0.5)
    with pytest.raises(RepositoryError, match="Could not reach"):
        repo.list_tasks()


def test_client_mode_cli_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI in client mode exits non-zero when the server is unreachable."""
    from typer.testing import CliRunner

    from systema2.cli import app as cli_app

    monkeypatch.setenv("SYSTEMA2_MODE", "client")
    monkeypatch.setenv("SYSTEMA2_API_URL", "http://127.0.0.1:1")

    runner = CliRunner()
    result = runner.invoke(cli_app, ["list"])
    # Exit code 2 is our chosen code for repository errors.
    assert result.exit_code == 2
    assert "Could not reach" in result.output
