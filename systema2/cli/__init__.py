"""systema2 CLI entrypoint (Typer)."""

from __future__ import annotations

import typer

from systema2.cli import serve as serve_cmd
from systema2.cli import tasks as tasks_cmd
from systema2.cli import tui as tui_cmd

app = typer.Typer(help="systema2 task manager CLI")

# Register task commands as top-level: systema2 create / update / delete / list
app.command("list")(tasks_cmd.list_tasks)
app.command("create")(tasks_cmd.create_task)
app.command("update")(tasks_cmd.update_task)
app.command("delete")(tasks_cmd.delete_task)
app.command("tui")(tui_cmd.launch_tui)
app.command("serve")(serve_cmd.serve)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
