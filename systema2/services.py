"""Task & Project service layer.

All DB access for Tasks and Projects lives here. Used by the HTTP API,
the Typer CLI, and the Textual TUI so CRUD logic stays in one place.

Functions raise domain errors (e.g. :class:`ProjectNotFoundError`) that
the API layer translates into HTTP responses.
"""

from __future__ import annotations

from sqlmodel import Session, select

from systema2 import database
from systema2.models import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    Task,
    TaskCreate,
    TaskUpdate,
    _utcnow,
)


class ProjectNotFoundError(LookupError):
    """Raised when an operation references a non-existent project."""

    def __init__(self, project_id: int) -> None:
        super().__init__(f"Project {project_id} not found")
        self.project_id = project_id


def _session() -> Session:
    # Resolve the engine lazily so tests can monkey-patch
    # ``systema2.database.engine``.
    return Session(database.engine)


def _assert_project_exists(session: Session, project_id: int | None) -> None:
    if project_id is None:
        return
    if session.get(Project, project_id) is None:
        raise ProjectNotFoundError(project_id)


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------


def list_tasks(
    session: Session,
    *,
    project_id: int | None = None,
    unassigned: bool = False,
) -> list[Task]:
    stmt = select(Task).order_by(Task.id)
    if unassigned:
        stmt = stmt.where(Task.project_id.is_(None))  # type: ignore[union-attr]
    elif project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    return list(session.exec(stmt).all())


def get_task(session: Session, task_id: int) -> Task | None:
    return session.get(Task, task_id)


def create_task(session: Session, payload: TaskCreate) -> Task:
    _assert_project_exists(session, payload.project_id)
    task = Task.model_validate(payload)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def update_task(
    session: Session, task_id: int, payload: TaskUpdate
) -> Task | None:
    task = session.get(Task, task_id)
    if task is None:
        return None

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return task

    if "project_id" in data:
        _assert_project_exists(session, data["project_id"])

    for key, value in data.items():
        setattr(task, key, value)
    task.updated_at = _utcnow()

    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def delete_task(session: Session, task_id: int) -> bool:
    task = session.get(Task, task_id)
    if task is None:
        return False
    session.delete(task)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


def list_projects(session: Session) -> list[Project]:
    return list(session.exec(select(Project).order_by(Project.id)).all())


def get_project(session: Session, project_id: int) -> Project | None:
    return session.get(Project, project_id)


def create_project(session: Session, payload: ProjectCreate) -> Project:
    project = Project.model_validate(payload)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def update_project(
    session: Session, project_id: int, payload: ProjectUpdate
) -> Project | None:
    project = session.get(Project, project_id)
    if project is None:
        return None

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return project

    for key, value in data.items():
        setattr(project, key, value)
    project.updated_at = _utcnow()

    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, project_id: int) -> bool:
    """Delete a project. Tasks in the project are unlinked (project_id=NULL)."""
    project = session.get(Project, project_id)
    if project is None:
        return False

    tasks = session.exec(
        select(Task).where(Task.project_id == project_id)
    ).all()
    for t in tasks:
        t.project_id = None
        t.updated_at = _utcnow()
        session.add(t)

    session.delete(project)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Convenience session-opening wrappers (used by CLI/TUI).
# ---------------------------------------------------------------------------


def list_tasks_std(
    *, project_id: int | None = None, unassigned: bool = False
) -> list[Task]:
    with _session() as s:
        return list_tasks(s, project_id=project_id, unassigned=unassigned)


def get_task_std(task_id: int) -> Task | None:
    with _session() as s:
        return get_task(s, task_id)


def create_task_std(payload: TaskCreate) -> Task:
    with _session() as s:
        return create_task(s, payload)


def update_task_std(task_id: int, payload: TaskUpdate) -> Task | None:
    with _session() as s:
        return update_task(s, task_id, payload)


def delete_task_std(task_id: int) -> bool:
    with _session() as s:
        return delete_task(s, task_id)


def list_projects_std() -> list[Project]:
    with _session() as s:
        return list_projects(s)


def get_project_std(project_id: int) -> Project | None:
    with _session() as s:
        return get_project(s, project_id)


def create_project_std(payload: ProjectCreate) -> Project:
    with _session() as s:
        return create_project(s, payload)


def update_project_std(
    project_id: int, payload: ProjectUpdate
) -> Project | None:
    with _session() as s:
        return update_project(s, project_id, payload)


def delete_project_std(project_id: int) -> bool:
    with _session() as s:
        return delete_project(s, project_id)
