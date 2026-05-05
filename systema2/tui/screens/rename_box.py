"""Rename-box modal for the whiteboard editor."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


_RENAME_CSS = """
RenameBoxScreen {
    align: center middle;
}

#dialog {
    width: 50;
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

#dialog #error { color: $error; padding-top: 1; height: auto; }
#dialog Horizontal { height: auto; align: right middle; padding-top: 1; }
#dialog Button { margin-left: 2; }
"""


class RenameBoxScreen(ModalScreen[str | None]):
    """Modal that prompts for a new box label.

    Dismisses with the new label string on success, or ``None`` if the
    user cancels.
    """

    DEFAULT_CSS = _RENAME_CSS
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Save"),
    ]

    def __init__(self, current_label: str) -> None:
        super().__init__()
        self._current_label = current_label

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Rename Box", classes="title")
            yield Input(
                value=self._current_label,
                placeholder="Box label (required)",
                id="label",
            )
            yield Static("", id="error")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Save", variant="primary", id="save")

    def on_mount(self) -> None:
        inp = self.query_one("#label", Input)
        inp.focus()
        # Pre-select the entire text so typing immediately replaces it.
        inp.action_select_all()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "save":
            self._submit()

    def _submit(self) -> None:
        label = self.query_one("#label", Input).value.strip()
        if not label:
            self.query_one("#error", Static).update(
                "Label cannot be empty."
            )
            return
        self.dismiss(label)
