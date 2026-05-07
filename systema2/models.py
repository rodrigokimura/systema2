from datetime import date, datetime, timezone
from enum import Enum

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from systema2.nanoid import nanoid


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
    id: str = Field(default_factory=nanoid, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectRead(ProjectBase):
    id: str
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
    due_date: date | None = Field(default=None, index=True)
    project_id: str | None = Field(
        default=None, foreign_key="project.id", index=True
    )


class Task(TaskBase, table=True):
    id: str = Field(default_factory=nanoid, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class TaskCreate(TaskBase):
    pass


class TaskUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    completed: bool | None = None
    priority: Priority | None = None
    # ``None`` means "clear"; omitted means "don't touch" (via exclude_unset).
    due_date: date | None = None
    project_id: str | None = None


class TaskRead(TaskBase):
    id: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Whiteboard / Box / Connector
#
# A Whiteboard is a free-form canvas. Boxes are placed on it at (x, y)
# character coordinates with a width/height. Connectors are directed
# links between two boxes on the same whiteboard; they are rendered
# automatically by the TUI.
# ---------------------------------------------------------------------------


class WhiteboardBase(SQLModel):
    name: str = Field(index=True, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class Whiteboard(WhiteboardBase, table=True):
    id: str = Field(default_factory=nanoid, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class WhiteboardCreate(WhiteboardBase):
    pass


class WhiteboardUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class WhiteboardRead(WhiteboardBase):
    id: str
    created_at: datetime
    updated_at: datetime


class BoxBase(SQLModel):
    label: str = Field(min_length=1, max_length=200)
    # Coordinates are in terminal character cells. Origin (0, 0) is the
    # top-left corner of the whiteboard canvas.
    x: int = Field(default=0, ge=0, le=1000)
    y: int = Field(default=0, ge=0, le=1000)
    width: int = Field(default=12, ge=3, le=200)
    height: int = Field(default=3, ge=3, le=100)
    whiteboard_id: str = Field(foreign_key="whiteboard.id", index=True)
    # Appearance
    border_style: str = Field(default="bold white", max_length=100)
    fill_style: str | None = Field(default=None, max_length=100)


class Box(BoxBase, table=True):
    id: str = Field(default_factory=nanoid, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class BoxCreate(BoxBase):
    pass


class BoxUpdate(SQLModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    x: int | None = Field(default=None, ge=0, le=1000)
    y: int | None = Field(default=None, ge=0, le=1000)
    width: int | None = Field(default=None, ge=3, le=200)
    height: int | None = Field(default=None, ge=3, le=100)
    border_style: str | None = Field(default=None, max_length=100)
    fill_style: str | None = Field(default=None, max_length=100)


class BoxRead(BoxBase):
    id: str
    created_at: datetime
    updated_at: datetime


class ConnectorBase(SQLModel):
    whiteboard_id: str = Field(foreign_key="whiteboard.id", index=True)
    source_box_id: str = Field(foreign_key="box.id", index=True)
    target_box_id: str = Field(foreign_key="box.id", index=True)
    label: str | None = Field(default=None, max_length=100)


class Connector(ConnectorBase, table=True):
    id: str = Field(default_factory=nanoid, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class ConnectorCreate(ConnectorBase):
    pass


class ConnectorUpdate(SQLModel):
    label: str | None = Field(default=None, max_length=100)


class ConnectorRead(ConnectorBase):
    id: str
    created_at: datetime
    updated_at: datetime
