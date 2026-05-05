from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from systema2 import services
from systema2.database import get_session
from systema2.models import (
    Project,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    Task,
    TaskRead,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_or_404(session: Session, project_id: str) -> Project:
    project = services.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(
    session: Session = Depends(get_session),
) -> list[Project]:
    return services.list_projects(session)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str, session: Session = Depends(get_session)
) -> Project:
    return _get_or_404(session, project_id)


@router.post(
    "", response_model=ProjectRead, status_code=status.HTTP_201_CREATED
)
def create_project(
    payload: ProjectCreate, session: Session = Depends(get_session)
) -> Project:
    return services.create_project(session, payload)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    session: Session = Depends(get_session),
) -> Project:
    project = services.update_project(session, project_id, payload)
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str, session: Session = Depends(get_session)
) -> None:
    if not services.delete_project(session, project_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Project not found"
        )


@router.get("/{project_id}/tasks", response_model=list[TaskRead])
def list_project_tasks(
    project_id: str, session: Session = Depends(get_session)
) -> list[Task]:
    _get_or_404(session, project_id)
    return services.list_tasks(session, project_id=project_id)
