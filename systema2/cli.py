from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select

from systema2.database import engine, init_db
from systema2.models import Task, TaskCreate, TaskUpdate, _utcnow

app = typer.Typer(help="systema2 task manager CLI")
console = Console()


def _ensure_db() -> None:
    init_db()


def _render_task(task: Task) -> None:
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


@app.command("list")
def list_tasks() -> None:
    """List all tasks."""
    _ensure_db()
    with Session(engine) as session:
        tasks = list(session.exec(select(Task).order_by(Task.id)).all())

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


@app.command("create")
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
    _ensure_db()
    payload = TaskCreate(title=title, description=description, completed=completed)
    task = Task.model_validate(payload)
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)

    console.print(f"[green]Created task {task.id}[/green]")
    _render_task(task)


@app.command("update")
def update_task(
    task_id: int = typer.Argument(..., help="ID of the task to update."),
    title: str | None = typer.Option(None, "--title", "-t"),
    description: str | None = typer.Option(None, "--description", "-d"),
    completed: bool | None = typer.Option(
        None, "--completed/--not-completed", help="Set completion status."
    ),
) -> None:
    """Update fields on an existing task. Only provided options are changed."""
    _ensure_db()
    # Build dict only from explicitly-provided options so unset ones don't
    # overwrite existing fields with None.
    raw: dict[str, object] = {}
    if title is not None:
        raw["title"] = title
    if description is not None:
        raw["description"] = description
    if completed is not None:
        raw["completed"] = completed

    # Validate via the TaskUpdate model.
    payload = TaskUpdate(**raw)
    data = payload.model_dump(exclude_unset=True)

    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None:
            console.print(f"[red]Task {task_id} not found[/red]")
            raise typer.Exit(code=1)

        if not data:
            console.print("[yellow]No changes specified.[/yellow]")
            _render_task(task)
            return

        for key, value in data.items():
            setattr(task, key, value)
        task.updated_at = _utcnow()

        session.add(task)
        session.commit()
        session.refresh(task)

    console.print(f"[green]Updated task {task.id}[/green]")
    _render_task(task)


@app.command("tui")
def launch_tui() -> None:
    """Launch the Textual TUI."""
    _ensure_db()
    # Imported lazily so `systema2 --help` doesn't pay the textual import cost.
    from systema2.tui import Systema2App

    Systema2App().run()


@app.command("delete")
def delete_task(
    task_id: int = typer.Argument(..., help="ID of the task to delete."),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt."
    ),
) -> None:
    """Delete a task by ID."""
    _ensure_db()
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None:
            console.print(f"[red]Task {task_id} not found[/red]")
            raise typer.Exit(code=1)

        if not yes:
            typer.confirm(
                f"Delete task {task.id} ({task.title!r})?", abort=True
            )

        session.delete(task)
        session.commit()

    console.print(f"[green]Deleted task {task_id}[/green]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
