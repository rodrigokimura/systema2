from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from systema2 import services
from systema2.database import get_session
from systema2.models import Priority, Task, TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_or_404(session: Session, task_id: int) -> Task:
    task = services.get_task(session, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(
    project_id: int | None = Query(
        None, description="Filter to tasks in this project."
    ),
    unassigned: bool = Query(
        False, description="If true, return only tasks with no project."
    ),
    priority: Priority | None = Query(
        None, description="Filter to tasks with this priority (H/M/L)."
    ),
    due_before: date | None = Query(
        None,
        description="Return only tasks with a due_date on or before this date.",
    ),
    session: Session = Depends(get_session),
) -> list[Task]:
    return services.list_tasks(
        session,
        project_id=project_id,
        unassigned=unassigned,
        priority=priority,
        due_before=due_before,
    )


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)) -> Task:
    return _get_or_404(session, task_id)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate, session: Session = Depends(get_session)
) -> Task:
    try:
        return services.create_task(session, payload)
    except services.ProjectNotFoundError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "project_not_found",
                "project_id": exc.project_id,
            },
        ) from exc


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: Session = Depends(get_session),
) -> Task:
    try:
        task = services.update_task(session, task_id, payload)
    except services.ProjectNotFoundError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "project_not_found",
                "project_id": exc.project_id,
            },
        ) from exc
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int, session: Session = Depends(get_session)
) -> None:
    if not services.delete_task(session, task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
