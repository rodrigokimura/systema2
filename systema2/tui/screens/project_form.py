"""Add/Edit project modal screens."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from systema2.models import Project, ProjectCreate, ProjectUpdate
from systema2.repository import RepositoryError, get_repository

FORM_CSS = """
ProjectFormScreen {
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


class ProjectFormScreen(ModalScreen[Project | None]):
    """Base modal for creating/editing a project."""

    DEFAULT_CSS = FORM_CSS
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Save"),
    ]

    def __init__(self, *, title: str, project: Project | None = None) -> None:
        super().__init__()
        self._title = title
        self._project_obj = project

    def compose(self) -> ComposeResult:
        p = self._project_obj
        initial_name = p.name if p else ""
        initial_desc = p.description if p and p.description else ""

        with Vertical(id="dialog"):
            yield Label(self._title, classes="title")
            yield Label("Name", classes="field")
            yield Input(
                value=initial_name,
                placeholder="Project name (required)",
                id="name",
            )
            yield Label("Description", classes="field")
            yield Input(
                value=initial_desc,
                placeholder="Optional description",
                id="description",
            )
            yield Static("", id="error")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Save", variant="primary", id="save")

    def on_mount(self) -> None:
        self.query_one("#name", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "save":
            self._submit()

    def _submit(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def _collect(self) -> tuple[str, str | None]:
        name = self.query_one("#name", Input).value.strip()
        desc_raw = self.query_one("#description", Input).value.strip()
        return name, desc_raw or None

    def _show_error(self, message: str) -> None:
        self.query_one("#error", Static).update(message)


class AddProjectScreen(ProjectFormScreen):
    def __init__(self) -> None:
        super().__init__(title="Add Project")

    def _submit(self) -> None:
        name, description = self._collect()
        try:
            payload = ProjectCreate(name=name, description=description)
        except Exception as exc:
            self._show_error(str(exc))
            return
        try:
            project = get_repository().create_project(payload)
        except RepositoryError as exc:
            self._show_error(str(exc))
            return
        self.dismiss(project)


class EditProjectScreen(ProjectFormScreen):
    def __init__(self, project: Project) -> None:
        super().__init__(title=f"Edit Project #{project.id}", project=project)
        self._project_id: str = project.id

    def _submit(self) -> None:
        name, description = self._collect()
        try:
            payload = ProjectUpdate(name=name, description=description)
        except Exception as exc:
            self._show_error(str(exc))
            return
        assert self._project_id is not None
        try:
            project = get_repository().update_project(self._project_id, payload)
        except RepositoryError as exc:
            self._show_error(str(exc))
            return
        if project is None:
            self._show_error("Project no longer exists.")
            return
        self.dismiss(project)
