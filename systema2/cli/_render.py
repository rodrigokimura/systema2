"""Shared Rich rendering helpers for the CLI."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from systema2.models import Task

console = Console()


def render_task(task: Task) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("id", str(task.id))
    table.add_row("title", task.title)
    table.add_row("description", task.description or "")
    table.add_row("completed", "✓" if task.completed else "✗")
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
    table.add_column("Done", justify="center")
    for t in tasks:
        table.add_row(
            str(t.id),
            t.title,
            t.description or "",
            "✓" if t.completed else "✗",
        )
    console.print(table)
