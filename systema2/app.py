from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlmodel import Session, select

from systema2.database import engine, get_session, init_db
from systema2.models import Task, TaskCreate, TaskRead, TaskUpdate
from systema2.models import _utcnow


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield
    engine.dispose()


app = FastAPI(title="systema2", lifespan=lifespan)


@app.get("/")
def root() -> dict[str, str]:
    return {"app": "systema2", "status": "ok"}


@app.get("/tasks", response_model=list[TaskRead])
def list_tasks(session: Session = Depends(get_session)) -> list[Task]:
    return list(session.exec(select(Task).order_by(Task.id)).all())


@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate, session: Session = Depends(get_session)
) -> Task:
    task = Task.model_validate(payload)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: Session = Depends(get_session),
) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")

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


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: Session = Depends(get_session)) -> None:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    session.delete(task)
    session.commit()
