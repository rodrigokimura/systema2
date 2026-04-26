"""Shared Rich rendering helpers for the CLI."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from systema2.models import Priority, Project, Task

console = Console()

_PRIORITY_STYLE: dict[Priority, str] = {
    Priority.HIGH: "bold red",
    Priority.MEDIUM: "yellow",
    Priority.LOW: "dim",
}


def _priority_cell(p: Priority) -> str:
    return f"[{_PRIORITY_STYLE[p]}]{p.value}[/{_PRIORITY_STYLE[p]}]"


def render_task(task: Task) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("id", str(task.id))
    table.add_row("title", task.title)
    table.add_row("description", task.description or "")
    table.add_row("completed", "✓" if task.completed else "✗")
    table.add_row("priority", _priority_cell(task.priority))
    table.add_row(
        "project_id", str(task.project_id) if task.project_id is not None else ""
    )
    table.add_row("created_at", task.created_at.isoformat())
    table.add_row("updated_at", task.updated_at.isoformat())
    console.print(table)


def render_task_list(tasks: list[Task]) -> None:
    if not tasks:
        console.print("[dim]No tasks.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", justify="right")
    table.add_column("Title")
    table.add_column("Description")
    table.add_column("Pri", justify="center")
    table.add_column("Project", justify="right")
    table.add_column("Done", justify="center")
    for t in tasks:
        table.add_row(
            str(t.id),
            t.title,
            t.description or "",
            _priority_cell(t.priority),
            str(t.project_id) if t.project_id is not None else "",
            "✓" if t.completed else "✗",
        )
    console.print(table)


def render_project(project: Project) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("id", str(project.id))
    table.add_row("name", project.name)
    table.add_row("description", project.description or "")
    table.add_row("created_at", project.created_at.isoformat())
    table.add_row("updated_at", project.updated_at.isoformat())
    console.print(table)


def render_project_list(projects: list[Project]) -> None:
    if not projects:
        console.print("[dim]No projects.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Description")
    for p in projects:
        table.add_row(str(p.id), p.name, p.description or "")
    console.print(table)
