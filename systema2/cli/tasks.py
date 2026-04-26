"""Task CRUD commands for the Typer CLI."""

from __future__ import annotations

import typer

from systema2.cli._render import console, render_task, render_task_list
from systema2.database import init_db_if_local
from systema2.models import Priority, TaskCreate, TaskUpdate
from systema2.repository import (
    ProjectNotFoundError,
    RepositoryError,
    get_repository,
)


def _repo():
    """Obtain repository, converting startup errors into CLI exits."""
    init_db_if_local()
    return get_repository()


def _handle_repo_error(exc: RepositoryError) -> None:
    console.print(f"[red]{exc}[/red]")
    raise typer.Exit(code=2)


def list_tasks(
    project: int | None = typer.Option(
        None, "--project", "-p", help="Filter to tasks in this project id."
    ),
    unassigned: bool = typer.Option(
        False, "--unassigned", help="Show only tasks with no project."
    ),
    priority: Priority | None = typer.Option(
        None, "--priority", "-P", help="Filter to this priority (H/M/L)."
    ),
) -> None:
    """List all tasks."""
    if project is not None and unassigned:
        console.print("[red]Use either --project or --unassigned, not both.[/red]")
        raise typer.Exit(code=2)

    repo = _repo()
    try:
        tasks = repo.list_tasks(
            project_id=project, unassigned=unassigned, priority=priority
        )
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    render_task_list(tasks)


def create_task(
    title: str = typer.Argument(..., help="Task title (1-200 chars)."),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Optional task description."
    ),
    completed: bool = typer.Option(
        False, "--completed/--not-completed", help="Mark task as completed."
    ),
    project: int | None = typer.Option(
        None, "--project", "-p", help="Assign to this project id."
    ),
    priority: Priority = typer.Option(
        Priority.MEDIUM,
        "--priority",
        "-P",
        help="Task priority: H (high), M (medium), L (low).",
    ),
) -> None:
    """Create a new task."""
    repo = _repo()
    payload = TaskCreate(
        title=title,
        description=description,
        completed=completed,
        priority=priority,
        project_id=project,
    )
    try:
        task = repo.create_task(payload)
    except ProjectNotFoundError as exc:
        console.print(f"[red]Project {exc.project_id} not found[/red]")
        raise typer.Exit(code=1)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    console.print(f"[green]Created task {task.id}[/green]")
    render_task(task)


def update_task(
    task_id: int = typer.Argument(..., help="ID of the task to update."),
    title: str | None = typer.Option(None, "--title", "-t"),
    description: str | None = typer.Option(None, "--description", "-d"),
    completed: bool | None = typer.Option(
        None, "--completed/--not-completed", help="Set completion status."
    ),
    project: int | None = typer.Option(
        None, "--project", "-p", help="Reassign to this project id."
    ),
    clear_project: bool = typer.Option(
        False, "--clear-project", help="Unassign the task from its project."
    ),
    priority: Priority | None = typer.Option(
        None, "--priority", "-P", help="Set task priority (H/M/L)."
    ),
) -> None:
    """Update fields on an existing task. Only provided options are changed."""
    if project is not None and clear_project:
        console.print(
            "[red]Use either --project or --clear-project, not both.[/red]"
        )
        raise typer.Exit(code=2)

    repo = _repo()
    raw: dict[str, object] = {}
    if title is not None:
        raw["title"] = title
    if description is not None:
        raw["description"] = description
    if completed is not None:
        raw["completed"] = completed
    if priority is not None:
        raw["priority"] = priority
    if project is not None:
        raw["project_id"] = project
    elif clear_project:
        raw["project_id"] = None

    payload = TaskUpdate(**raw)
    try:
        task = repo.update_task(task_id, payload)
    except ProjectNotFoundError as exc:
        console.print(f"[red]Project {exc.project_id} not found[/red]")
        raise typer.Exit(code=1)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return

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
    repo = _repo()
    try:
        task = repo.get_task(task_id)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    if task is None:
        console.print(f"[red]Task {task_id} not found[/red]")
        raise typer.Exit(code=1)

    if not yes:
        typer.confirm(f"Delete task {task.id} ({task.title!r})?", abort=True)

    try:
        repo.delete_task(task_id)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    console.print(f"[green]Deleted task {task_id}[/green]")
