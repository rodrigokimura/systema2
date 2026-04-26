"""Task service layer.

Plain functions that own all DB access for Tasks. Used by the HTTP API,
the Typer CLI, and the Textual TUI so CRUD logic lives in exactly one place.

API-exposed functions return ORM objects (or None) and never raise HTTP
errors; translation to HTTP responses happens in the API layer.
"""

from __future__ import annotations

from sqlmodel import Session, select

from systema2 import database
from systema2.models import Task, TaskCreate, TaskUpdate, _utcnow


def list_tasks(session: Session) -> list[Task]:
    return list(session.exec(select(Task).order_by(Task.id)).all())


def get_task(session: Session, task_id: int) -> Task | None:
    return session.get(Task, task_id)


def create_task(session: Session, payload: TaskCreate) -> Task:
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
# Convenience wrappers that open their own session against the module-level
# engine. Used by the CLI and TUI, which don't have a request-scoped session.
# ---------------------------------------------------------------------------


def _session() -> Session:
    # Resolve the engine lazily so tests can monkey-patch
    # `systema2.database.engine`.
    return Session(database.engine)


def list_tasks_std() -> list[Task]:
    with _session() as session:
        return list_tasks(session)


def get_task_std(task_id: int) -> Task | None:
    with _session() as session:
        return get_task(session, task_id)


def create_task_std(payload: TaskCreate) -> Task:
    with _session() as session:
        return create_task(session, payload)


def update_task_std(task_id: int, payload: TaskUpdate) -> Task | None:
    with _session() as session:
        return update_task(session, task_id, payload)


def delete_task_std(task_id: int) -> bool:
    with _session() as session:
        return delete_task(session, task_id)
