"""Task CRUD commands for the Typer CLI."""

from __future__ import annotations

import typer

from systema2 import services
from systema2.cli._render import console, render_task, render_task_list
from systema2.database import init_db
from systema2.models import TaskCreate, TaskUpdate


def list_tasks() -> None:
    """List all tasks."""
    init_db()
    render_task_list(services.list_tasks_std())


def create_task(
    title: str = typer.Argument(..., help="Task title (1-200 chars)."),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Optional task description."
    ),
    completed: bool = typer.Option(
        False, "--completed/--not-completed", help="Mark task as completed."
    ),
) -> None:
    """Create a new task."""
    init_db()
    payload = TaskCreate(title=title, description=description, completed=completed)
    task = services.create_task_std(payload)
    console.print(f"[green]Created task {task.id}[/green]")
    render_task(task)


def update_task(
    task_id: int = typer.Argument(..., help="ID of the task to update."),
    title: str | None = typer.Option(None, "--title", "-t"),
    description: str | None = typer.Option(None, "--description", "-d"),
    completed: bool | None = typer.Option(
        None, "--completed/--not-completed", help="Set completion status."
    ),
) -> None:
    """Update fields on an existing task. Only provided options are changed."""
    init_db()
    # Build dict only from explicitly-provided options so unset ones don't
    # overwrite existing fields with None.
    raw: dict[str, object] = {}
    if title is not None:
        raw["title"] = title
    if description is not None:
        raw["description"] = description
    if completed is not None:
        raw["completed"] = completed

    payload = TaskUpdate(**raw)
    task = services.update_task_std(task_id, payload)
    if task is None:
        console.print(f"[red]Task {task_id} not found[/red]")
        raise typer.Exit(code=1)

    if not raw:
        console.print("[yellow]No changes specified.[/yellow]")
    else:
        console.print(f"[green]Updated task {task.id}[/green]")
    render_task(task)


def delete_task(
    task_id: int = typer.Argument(..., help="ID of the task to delete."),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt."
    ),
) -> None:
    """Delete a task by ID."""
    init_db()
    task = services.get_task_std(task_id)
    if task is None:
        console.print(f"[red]Task {task_id} not found[/red]")
        raise typer.Exit(code=1)

    if not yes:
        typer.confirm(f"Delete task {task.id} ({task.title!r})?", abort=True)

    services.delete_task_std(task_id)
    console.print(f"[green]Deleted task {task_id}[/green]")
