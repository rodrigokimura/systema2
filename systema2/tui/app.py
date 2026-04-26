"""Main Textual application shell for systema2."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header

from systema2.database import init_db_if_local
from systema2.models import Task
from systema2.repository import RepositoryError, get_repository
from systema2.tui.screens.delete import DeleteTaskScreen
from systema2.tui.screens.form import AddTaskScreen, EditTaskScreen


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
        init_db_if_local()
        self._repo = get_repository()
        table = self.query_one(DataTable)
        table.add_columns("ID", "Title", "Description", "Done")
        self._reload()

    # ---- data ----------------------------------------------------------

    def _reload(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        try:
            tasks = self._repo.list_tasks()
        except RepositoryError as exc:
            self.notify(str(exc), severity="error", timeout=6.0)
            return
        for t in tasks:
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

    def _require_selected_task(self) -> Task | None:
        """Return the selected task or notify the user and return None."""
        task_id = self._selected_task_id()
        if task_id is None:
            self.notify("No task selected.", severity="warning")
            return None
        try:
            task = self._repo.get_task(task_id)
        except RepositoryError as exc:
            self.notify(str(exc), severity="error", timeout=6.0)
            return None
        if task is None:
            self.notify("Task not found.", severity="error")
            self._reload()
            return None
        return task

    # ---- actions -------------------------------------------------------

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
        task = self._require_selected_task()
        if task is None:
            return

        def _after(updated: Task | None) -> None:
            if updated is not None:
                self._reload()
                self.notify(f"Updated task {updated.id}.")

        self.push_screen(EditTaskScreen(task), _after)

    def action_delete_task(self) -> None:
        task = self._require_selected_task()
        if task is None:
            return

        def _after(confirmed: bool | None) -> None:
            if confirmed:
                self._reload()
                self.notify(f"Deleted task {task.id}.")

        self.push_screen(DeleteTaskScreen(task), _after)


def main() -> None:
    Systema2App().run()


if __name__ == "__main__":
    main()
