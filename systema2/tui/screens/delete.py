"""Delete confirmation modals for tasks and projects."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from systema2.models import Project, Task
from systema2.repository import RepositoryError, get_repository


_DELETE_CSS = """
$self {
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
#dialog Button { margin: 0 1; }
"""


class _ConfirmDeleteScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    _message: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._message)
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

    def _confirm(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class DeleteTaskScreen(_ConfirmDeleteScreen):
    """Confirmation modal for deleting a task."""

    DEFAULT_CSS = _DELETE_CSS.replace("$self", "DeleteTaskScreen")

    def __init__(self, task: Task) -> None:
        super().__init__()
        self._task_obj = task
        self._message = (
            f"Delete task #{task.id} ({task.title!r})?"
        )

    def _confirm(self) -> None:
        assert self._task_obj.id is not None
        try:
            get_repository().delete_task(self._task_obj.id)
        except RepositoryError:
            self.dismiss(False)
            return
        self.dismiss(True)


class DeleteProjectScreen(_ConfirmDeleteScreen):
    """Confirmation modal for deleting a project."""

    DEFAULT_CSS = _DELETE_CSS.replace("$self", "DeleteProjectScreen")

    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project_obj = project
        self._message = (
            f"Delete project #{project.id} ({project.name!r})? "
            "Its tasks will be unassigned."
        )

    def _confirm(self) -> None:
        assert self._project_obj.id is not None
        try:
            get_repository().delete_project(self._project_obj.id)
        except RepositoryError:
            self.dismiss(False)
            return
        self.dismiss(True)
