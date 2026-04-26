"""Project CRUD commands for the Typer CLI."""

from __future__ import annotations

import typer

from systema2.cli._render import (
    console,
    render_project,
    render_project_list,
    render_task_list,
)
from systema2.database import init_db_if_local
from systema2.models import ProjectCreate, ProjectUpdate
from systema2.repository import RepositoryError, get_repository

app = typer.Typer(help="Project management")


def _repo():
    init_db_if_local()
    return get_repository()


def _handle_repo_error(exc: RepositoryError) -> None:
    console.print(f"[red]{exc}[/red]")
    raise typer.Exit(code=2)


@app.command("list")
def list_projects() -> None:
    """List all projects."""
    repo = _repo()
    try:
        projects = repo.list_projects()
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    render_project_list(projects)


@app.command("show")
def show_project(
    project_id: int = typer.Argument(..., help="Project ID."),
    with_tasks: bool = typer.Option(
        False, "--with-tasks", help="Also list the project's tasks."
    ),
) -> None:
    """Show a single project, optionally with its tasks."""
    repo = _repo()
    try:
        project = repo.get_project(project_id)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    if project is None:
        console.print(f"[red]Project {project_id} not found[/red]")
        raise typer.Exit(code=1)

    render_project(project)

    if with_tasks:
        try:
            tasks = repo.list_tasks(project_id=project_id)
        except RepositoryError as exc:
            _handle_repo_error(exc)
            return
        console.print("[bold]Tasks[/bold]")
        render_task_list(tasks)


@app.command("create")
def create_project(
    name: str = typer.Argument(..., help="Project name (1-200 chars)."),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Optional project description."
    ),
) -> None:
    """Create a new project."""
    repo = _repo()
    payload = ProjectCreate(name=name, description=description)
    try:
        project = repo.create_project(payload)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    console.print(f"[green]Created project {project.id}[/green]")
    render_project(project)


@app.command("update")
def update_project(
    project_id: int = typer.Argument(..., help="ID of the project to update."),
    name: str | None = typer.Option(None, "--name", "-n"),
    description: str | None = typer.Option(None, "--description", "-d"),
) -> None:
    """Update fields on an existing project."""
    repo = _repo()
    raw: dict[str, object] = {}
    if name is not None:
        raw["name"] = name
    if description is not None:
        raw["description"] = description

    payload = ProjectUpdate(**raw)
    try:
        project = repo.update_project(project_id, payload)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    if project is None:
        console.print(f"[red]Project {project_id} not found[/red]")
        raise typer.Exit(code=1)

    if not raw:
        console.print("[yellow]No changes specified.[/yellow]")
    else:
        console.print(f"[green]Updated project {project.id}[/green]")
    render_project(project)


@app.command("delete")
def delete_project(
    project_id: int = typer.Argument(..., help="ID of the project to delete."),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt."
    ),
) -> None:
    """Delete a project. Tasks in the project are unlinked (not deleted)."""
    repo = _repo()
    try:
        project = repo.get_project(project_id)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    if project is None:
        console.print(f"[red]Project {project_id} not found[/red]")
        raise typer.Exit(code=1)

    if not yes:
        typer.confirm(
            f"Delete project {project.id} ({project.name!r})? "
            f"Its tasks will be unassigned.",
            abort=True,
        )

    try:
        repo.delete_project(project_id)
    except RepositoryError as exc:
        _handle_repo_error(exc)
        return
    console.print(f"[green]Deleted project {project_id}[/green]")
