"""Textual TUI for systema2 task management."""

from __future__ import annotations

from sqlmodel import Session, select

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from systema2.database import engine, init_db
from systema2.models import Task, TaskCreate, TaskUpdate, _utcnow


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_tasks() -> list[Task]:
    with Session(engine) as session:
        return list(session.exec(select(Task).order_by(Task.id)).all())


def _fetch_task(task_id: int) -> Task | None:
    with Session(engine) as session:
        return session.get(Task, task_id)


def _create_task(payload: TaskCreate) -> Task:
    task = Task.model_validate(payload)
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def _update_task(task_id: int, payload: TaskUpdate) -> Task | None:
    data = payload.model_dump(exclude_unset=True)
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None:
            return None
        for key, value in data.items():
            setattr(task, key, value)
        task.updated_at = _utcnow()
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def _delete_task(task_id: int) -> bool:
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None:
            return False
        session.delete(task)
        session.commit()
        return True


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------

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

#dialog Label.field {
    padding-top: 1;
}

#dialog #error {
    color: $error;
    padding-top: 1;
    height: auto;
}

#dialog Horizontal {
    height: auto;
    align: right middle;
    padding-top: 1;
}

#dialog Button {
    margin-left: 2;
}
"""


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
    ) -> None:
        super().__init__()
        self._title = title
        # NOTE: don't use `self._task` — Textual's MessagePump owns that name.
        self._task_obj = task

    def compose(self) -> ComposeResult:
        initial_title = self._task_obj.title if self._task_obj else ""
        initial_desc = (
            self._task_obj.description
            if self._task_obj and self._task_obj.description
            else ""
        )
        initial_completed = (
            bool(self._task_obj.completed) if self._task_obj else False
        )

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
            yield Checkbox("Completed", value=initial_completed, id="completed")
            yield Static("", id="error")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Save", variant="primary", id="save")

    def on_mount(self) -> None:
        self.query_one("#title", Input).focus()

    # ---- actions --------------------------------------------------------

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "save":
            self._submit()

    # ---- hook for subclasses -------------------------------------------

    def _submit(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def _collect(self) -> tuple[str, str | None, bool]:
        title = self.query_one("#title", Input).value.strip()
        desc_raw = self.query_one("#description", Input).value.strip()
        completed = self.query_one("#completed", Checkbox).value
        description = desc_raw or None
        return title, description, completed

    def _show_error(self, message: str) -> None:
        self.query_one("#error", Static).update(message)


class AddTaskScreen(TaskFormScreen):
    def __init__(self) -> None:
        super().__init__(title="Add Task")

    def _submit(self) -> None:
        title, description, completed = self._collect()
        try:
            payload = TaskCreate(
                title=title, description=description, completed=completed
            )
        except Exception as exc:  # pydantic ValidationError
            self._show_error(str(exc))
            return
        task = _create_task(payload)
        self.dismiss(task)


class EditTaskScreen(TaskFormScreen):
    def __init__(self, task: Task) -> None:
        super().__init__(title=f"Edit Task #{task.id}", task=task)
        # Cache the id separately — avoid `self._task` (reserved by Textual).
        self._task_id = task.id

    def _submit(self) -> None:
        title, description, completed = self._collect()
        try:
            payload = TaskUpdate(
                title=title, description=description, completed=completed
            )
        except Exception as exc:
            self._show_error(str(exc))
            return
        assert self._task_id is not None
        task = _update_task(self._task_id, payload)
        if task is None:
            self._show_error("Task no longer exists.")
            return
        self.dismiss(task)


class DeleteTaskScreen(ModalScreen[bool]):
    """Confirmation modal for deleting a task."""

    DEFAULT_CSS = """
    DeleteTaskScreen {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $error;
    }
    #dialog Label {
        width: 100%;
        content-align: center middle;
        padding: 1 0;
    }
    #dialog Horizontal {
        height: auto;
        align: center middle;
        padding-top: 1;
    }
    #dialog Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    def __init__(self, task: Task) -> None:
        super().__init__()
        # NOTE: don't use `self._task` — Textual's MessagePump owns that name.
        self._task_obj = task

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(
                f"Delete task #{self._task_obj.id} ({self._task_obj.title!r})?"
            )
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Delete", variant="error", id="delete")

    def on_mount(self) -> None:
        self.query_one("#cancel", Button).focus()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self._confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(False)
        elif event.button.id == "delete":
            self._confirm()

    def _confirm(self) -> None:
        assert self._task_obj.id is not None
        _delete_task(self._task_obj.id)
        self.dismiss(True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


class Systema2App(App[None]):
    """Textual TUI for systema2."""

    CSS = """
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("a", "add_task", "Add"),
        Binding("e", "edit_task", "Edit"),
        Binding("d", "delete_task", "Delete"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "systema2"

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="tasks", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        init_db()
        table = self.query_one(DataTable)
        table.add_columns("ID", "Title", "Description", "Done")
        self._reload()

    # ---- data -----------------------------------------------------------

    def _reload(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for t in _fetch_tasks():
            table.add_row(
                str(t.id),
                t.title,
                t.description or "",
                "✓" if t.completed else "✗",
                key=str(t.id),
            )

    def _selected_task_id(self) -> int | None:
        table = self.query_one(DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        except Exception:
            return None
        if row_key.value is None:
            return None
        try:
            return int(row_key.value)
        except ValueError:
            return None

    # ---- actions --------------------------------------------------------

    def action_refresh(self) -> None:
        self._reload()
        self.notify("Refreshed.")

    def action_add_task(self) -> None:
        def _after(task: Task | None) -> None:
            if task is not None:
                self._reload()
                self.notify(f"Created task {task.id}.")

        self.push_screen(AddTaskScreen(), _after)

    def action_edit_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            self.notify("No task selected.", severity="warning")
            return
        task = _fetch_task(task_id)
        if task is None:
            self.notify("Task not found.", severity="error")
            self._reload()
            return

        def _after(updated: Task | None) -> None:
            if updated is not None:
                self._reload()
                self.notify(f"Updated task {updated.id}.")

        self.push_screen(EditTaskScreen(task), _after)

    def action_delete_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            self.notify("No task selected.", severity="warning")
            return
        task = _fetch_task(task_id)
        if task is None:
            self.notify("Task not found.", severity="error")
            self._reload()
            return

        def _after(confirmed: bool | None) -> None:
            if confirmed:
                self._reload()
                self.notify(f"Deleted task {task_id}.")

        self.push_screen(DeleteTaskScreen(task), _after)


def main() -> None:
    Systema2App().run()


if __name__ == "__main__":
    main()
