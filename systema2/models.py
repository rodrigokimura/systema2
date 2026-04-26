from datetime import datetime, timezone
from enum import Enum

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Priority(str, Enum):
    """Task priority: High, Medium, Low (default Medium)."""

    HIGH = "H"
    MEDIUM = "M"
    LOW = "L"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectBase(SQLModel):
    name: str = Field(index=True, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class Project(ProjectBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectRead(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


# Store the enum *value* ("H"/"M"/"L") rather than the name ("HIGH"/...),
# so what's on disk matches the API representation. ``values_callable``
# tells SQLAlchemy to persist ``e.value`` for each member.
def _priority_sa_column() -> sa.Column:
    return sa.Column(
        sa.Enum(
            Priority,
            name="priority",
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        index=True,
    )


class TaskBase(SQLModel):
    title: str = Field(index=True, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    completed: bool = False
    priority: Priority = Field(
        default=Priority.MEDIUM,
        sa_column=_priority_sa_column(),
    )
    project_id: int | None = Field(
        default=None, foreign_key="project.id", index=True
    )


class Task(TaskBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class TaskCreate(TaskBase):
    pass


class TaskUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    completed: bool | None = None
    priority: Priority | None = None
    # ``None`` means "unassign"; omitted means "don't touch" (via exclude_unset).
    project_id: int | None = None


class TaskRead(TaskBase):
    id: int
    created_at: datetime
    updated_at: datetime
