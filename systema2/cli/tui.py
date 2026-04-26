"""`systema2 tui` command: launch the Textual app."""

from __future__ import annotations

from systema2.database import init_db


def launch_tui() -> None:
    """Launch the Textual TUI."""
    init_db()
    # Imported lazily so `systema2 --help` doesn't pay the textual import cost.
    from systema2.tui import Systema2App

    Systema2App().run()
