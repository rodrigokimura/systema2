"""Main Textual application shell for systema2."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, ListItem, ListView, Label

from systema2.database import init_db_if_local
from systema2.models import Project, Task
from systema2.repository import RepositoryError, get_repository
from systema2.tui.screens.delete import DeleteProjectScreen, DeleteTaskScreen
from systema2.tui.screens.form import AddTaskScreen, EditTaskScreen
from systema2.tui.screens.project_form import AddProjectScreen, EditProjectScreen

# Sentinels for the sidebar
_ALL = "all"
_UNASSIGNED = "unassigned"


class Systema2App(App[None]):
    """Textual TUI for systema2."""

    CSS = """
    #layout {
        height: 1fr;
    }
    #projects {
        width: 32;
        border-right: solid $accent;
    }
    #projects > ListView {
        height: 1fr;
    }
    #tasks {
        width: 1fr;
    }
    """

    BINDINGS = [
        # Tasks
        Binding("a", "add_task", "Add task"),
        Binding("e", "edit_task", "Edit task"),
        Binding("d", "delete_task", "Delete task"),
        # Projects
        Binding("n", "add_project", "New project"),
        Binding("E", "edit_project", "Edit project"),
        Binding("x", "delete_project", "Delete project"),
        # Navigation
        Binding("tab", "focus_next_pane", "Switch pane"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "systema2"

    def __init__(self) -> None:
        super().__init__()
        self._projects: list[Project] = []
        # Sidebar selection: _ALL, _UNASSIGNED, or int project id.
        self._filter: object = _ALL

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="layout"):
            with Horizontal(id="projects"):
                yield ListView(id="project_list")
            yield DataTable(id="tasks", cursor_type="row", zebra_stripes=True)
        yield Footer()

    async def on_mount(self) -> None:
        init_db_if_local()
        self._repo = get_repository()

        table = self.query_one(DataTable)
        table.add_columns("ID", "Title", "Description", "Done")

        await self._reload_projects()
        self._reload_tasks()

    # ------------------------------------------------------------------
    # sidebar
    # ------------------------------------------------------------------

    def _sidebar(self) -> ListView:
        return self.query_one("#project_list", ListView)

    def _filter_for_index(self, index: int) -> object:
        """Map a sidebar row index to a filter value."""
        if index == 0:
            return _ALL
        if index == 1:
            return _UNASSIGNED
        project_idx = index - 2
        if 0 <= project_idx < len(self._projects):
            pid = self._projects[project_idx].id
            assert pid is not None
            return pid
        return _ALL

    async def _reload_projects(self) -> None:
        try:
            projects = self._repo.list_projects()
        except RepositoryError as exc:
            self.notify(str(exc), severity="error", timeout=6.0)
            projects = []
        self._projects = projects

        lv = self._sidebar()
        # Remember current filter to restore selection index if possible.
        prev_filter = self._filter

        # clear() returns AwaitRemove — await it so the old items are gone
        # before we append the new ones (otherwise ID collisions).
        await lv.clear()
        await lv.append(ListItem(Label("All tasks")))
        await lv.append(ListItem(Label("No project")))
        for p in projects:
            await lv.append(ListItem(Label(f"#{p.id} {p.name}")))

        # Restore selection
        target_index = 0
        if prev_filter == _UNASSIGNED:
            target_index = 1
        elif isinstance(prev_filter, int):
            for i, p in enumerate(projects):
                if p.id == prev_filter:
                    target_index = 2 + i
                    break
            else:
                target_index = 0
                self._filter = _ALL
        lv.index = target_index

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        lv = self._sidebar()
        if lv.index is None:
            return
        new_filter = self._filter_for_index(lv.index)
        if new_filter != self._filter:
            self._filter = new_filter
            self._reload_tasks()

    # ------------------------------------------------------------------
    # tasks
    # ------------------------------------------------------------------

    def _reload_tasks(self) -> None:
        table = self.query_one(DataTable)
        table.clear()

        kwargs: dict[str, object] = {}
        if self._filter == _UNASSIGNED:
            kwargs["unassigned"] = True
        elif isinstance(self._filter, int):
            kwargs["project_id"] = self._filter

        try:
            tasks = self._repo.list_tasks(**kwargs)  # type: ignore[arg-type]
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
            self._reload_tasks()
            return None
        return task

    def _current_project_id(self) -> int | None:
        """Return the project id to preselect in new-task forms."""
        if isinstance(self._filter, int):
            return self._filter
        return None

    def _require_selected_project(self) -> Project | None:
        lv = self._sidebar()
        if lv.index is None or lv.index < 2:
            self.notify(
                "Select a project in the sidebar first.", severity="warning"
            )
            return None
        idx = lv.index - 2
        if idx >= len(self._projects):
            return None
        project = self._projects[idx]
        assert project.id is not None
        try:
            fresh = self._repo.get_project(project.id)
        except RepositoryError as exc:
            self.notify(str(exc), severity="error", timeout=6.0)
            return None
        if fresh is None:
            self.notify("Project not found.", severity="error")
            # Reload will happen on next refresh/action; don't await here.
            return None
        return fresh

    # ------------------------------------------------------------------
    # actions — tasks
    # ------------------------------------------------------------------

    async def action_refresh(self) -> None:
        await self._reload_projects()
        self._reload_tasks()
        self.notify("Refreshed.")

    def action_focus_next_pane(self) -> None:
        table = self.query_one(DataTable)
        sidebar = self._sidebar()
        if self.focused is sidebar:
            table.focus()
        else:
            sidebar.focus()

    def action_add_task(self) -> None:
        def _after(task: Task | None) -> None:
            if task is not None:
                self._reload_tasks()
                self.notify(f"Created task {task.id}.")

        self.push_screen(
            AddTaskScreen(
                projects=self._projects,
                default_project_id=self._current_project_id(),
            ),
            _after,
        )

    def action_edit_task(self) -> None:
        task = self._require_selected_task()
        if task is None:
            return

        def _after(updated: Task | None) -> None:
            if updated is not None:
                self._reload_tasks()
                self.notify(f"Updated task {updated.id}.")

        self.push_screen(
            EditTaskScreen(task, projects=self._projects), _after
        )

    def action_delete_task(self) -> None:
        task = self._require_selected_task()
        if task is None:
            return

        def _after(confirmed: bool | None) -> None:
            if confirmed:
                self._reload_tasks()
                self.notify(f"Deleted task {task.id}.")

        self.push_screen(DeleteTaskScreen(task), _after)

    # ------------------------------------------------------------------
    # actions — projects
    # ------------------------------------------------------------------

    def action_add_project(self) -> None:
        async def _after(project: Project | None) -> None:
            if project is not None:
                await self._reload_projects()
                self.notify(f"Created project {project.id}.")

        self.push_screen(AddProjectScreen(), _after)

    def action_edit_project(self) -> None:
        project = self._require_selected_project()
        if project is None:
            return

        async def _after(updated: Project | None) -> None:
            if updated is not None:
                await self._reload_projects()
                self.notify(f"Updated project {updated.id}.")

        self.push_screen(EditProjectScreen(project), _after)

    def action_delete_project(self) -> None:
        project = self._require_selected_project()
        if project is None:
            return

        async def _after(confirmed: bool | None) -> None:
            if confirmed:
                # Selection will fall back to "All tasks".
                self._filter = _ALL
                await self._reload_projects()
                self._reload_tasks()
                self.notify(f"Deleted project {project.id}.")

        self.push_screen(DeleteProjectScreen(project), _after)


def main() -> None:
    Systema2App().run()


if __name__ == "__main__":
    main()
