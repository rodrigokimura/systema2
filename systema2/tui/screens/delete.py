"""Delete confirmation modal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from systema2 import services
from systema2.models import Task


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
        services.delete_task_std(self._task_obj.id)
        self.dismiss(True)
