"""Add/Edit task modal screens."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from systema2.models import Priority, Project, Task, TaskCreate, TaskUpdate
from systema2.repository import (
    ProjectNotFoundError,
    RepositoryError,
    get_repository,
)

FORM_CSS = """
TaskFormScreen {
    align: center middle;
}

#dialog {
    width: 60;
    height: auto;
    padding: 1 2;
    background: $surface;
    border: thick $accent;
}

#dialog Label.title {
    text-style: bold;
    width: 100%;
    content-align: center middle;
    padding-bottom: 1;
}

#dialog Label.field { padding-top: 1; }
#dialog #error { color: $error; padding-top: 1; height: auto; }
#dialog Horizontal { height: auto; align: right middle; padding-top: 1; }
#dialog Button { margin-left: 2; }
"""

# Sentinel value used in Select for "no project".
_NO_PROJECT = 0

_PRIORITY_OPTIONS: list[tuple[str, str]] = [
    ("High (H)", Priority.HIGH.value),
    ("Medium (M)", Priority.MEDIUM.value),
    ("Low (L)", Priority.LOW.value),
]


class TaskFormScreen(ModalScreen[Task | None]):
    """Base modal for creating/editing a task."""

    DEFAULT_CSS = FORM_CSS
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Save"),
    ]

    def __init__(
        self,
        *,
        title: str,
        task: Task | None = None,
        projects: list[Project] | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        # NOTE: don't use `self._task` — Textual's MessagePump owns that name.
        self._task_obj = task
        self._projects = projects or []

    # ---- project select helpers ---------------------------------------

    def _project_options(self) -> list[tuple[str, int]]:
        opts: list[tuple[str, int]] = [("(no project)", _NO_PROJECT)]
        for p in self._projects:
            label = f"#{p.id} {p.name}"
            assert p.id is not None
            opts.append((label, p.id))
        return opts

    def _initial_project_value(self) -> int:
        if self._task_obj and self._task_obj.project_id is not None:
            return self._task_obj.project_id
        return _NO_PROJECT

    def _selected_project_id(self) -> int | None:
        value = self.query_one("#project", Select).value
        if value == Select.BLANK or value == _NO_PROJECT:
            return None
        return int(value)  # type: ignore[arg-type]

    # ---- compose ------------------------------------------------------

    def _initial_priority(self) -> str:
        if self._task_obj is not None:
            return self._task_obj.priority.value
        return Priority.MEDIUM.value

    def compose(self) -> ComposeResult:
        t = self._task_obj
        initial_title = t.title if t else ""
        initial_desc = t.description if t and t.description else ""
        initial_completed = bool(t.completed) if t else False

        with Vertical(id="dialog"):
            yield Label(self._title, classes="title")
            yield Label("Title", classes="field")
            yield Input(
                value=initial_title,
                placeholder="Task title (required)",
                id="title",
            )
            yield Label("Description", classes="field")
            yield Input(
                value=initial_desc,
                placeholder="Optional description",
                id="description",
            )
            yield Label("Priority", classes="field")
            yield Select(
                options=_PRIORITY_OPTIONS,
                value=self._initial_priority(),
                allow_blank=False,
                id="priority",
            )
            yield Label("Project", classes="field")
            yield Select(
                options=self._project_options(),
                value=self._initial_project_value(),
                allow_blank=False,
                id="project",
            )
            yield Checkbox("Completed", value=initial_completed, id="completed")
            yield Static("", id="error")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Save", variant="primary", id="save")

    def on_mount(self) -> None:
        self.query_one("#title", Input).focus()

    # ---- actions ------------------------------------------------------

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "save":
            self._submit()

    # ---- subclass hook ------------------------------------------------

    def _submit(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def _collect(self) -> tuple[str, str | None, bool, Priority, int | None]:
        title = self.query_one("#title", Input).value.strip()
        desc_raw = self.query_one("#description", Input).value.strip()
        completed = self.query_one("#completed", Checkbox).value
        priority_value = self.query_one("#priority", Select).value
        priority = Priority(priority_value)  # type: ignore[arg-type]
        project_id = self._selected_project_id()
        return title, desc_raw or None, completed, priority, project_id

    def _show_error(self, message: str) -> None:
        self.query_one("#error", Static).update(message)


class AddTaskScreen(TaskFormScreen):
    def __init__(
        self,
        *,
        projects: list[Project] | None = None,
        default_project_id: int | None = None,
    ) -> None:
        super().__init__(title="Add Task", projects=projects)
        self._default_project_id = default_project_id

    def _initial_project_value(self) -> int:  # type: ignore[override]
        if self._default_project_id is not None:
            return self._default_project_id
        return super()._initial_project_value()

    def _submit(self) -> None:
        title, description, completed, priority, project_id = self._collect()
        try:
            payload = TaskCreate(
                title=title,
                description=description,
                completed=completed,
                priority=priority,
                project_id=project_id,
            )
        except Exception as exc:  # pydantic ValidationError
            self._show_error(str(exc))
            return
        try:
            task = get_repository().create_task(payload)
        except ProjectNotFoundError as exc:
            self._show_error(f"Project {exc.project_id} not found")
            return
        except RepositoryError as exc:
            self._show_error(str(exc))
            return
        self.dismiss(task)


class EditTaskScreen(TaskFormScreen):
    def __init__(
        self,
        task: Task,
        *,
        projects: list[Project] | None = None,
    ) -> None:
        super().__init__(
            title=f"Edit Task #{task.id}", task=task, projects=projects
        )
        self._task_id = task.id

    def _submit(self) -> None:
        title, description, completed, priority, project_id = self._collect()
        try:
            payload = TaskUpdate(
                title=title,
                description=description,
                completed=completed,
                priority=priority,
                project_id=project_id,
            )
        except Exception as exc:
            self._show_error(str(exc))
            return
        assert self._task_id is not None
        try:
            task = get_repository().update_task(self._task_id, payload)
        except ProjectNotFoundError as exc:
            self._show_error(f"Project {exc.project_id} not found")
            return
        except RepositoryError as exc:
            self._show_error(str(exc))
            return
        if task is None:
            self._show_error("Task no longer exists.")
            return
        self.dismiss(task)
