"""Module picker: the TUI's landing screen.

Shown immediately after the app mounts. Lets the user pick which
module to enter (Tasks or Whiteboards). It is a full-screen modal so
that the underlying module screens render beneath it on dismiss.

Navigation:

* ``t`` \u2014 enter the Tasks module (pops this screen to reveal the
  default tasks/projects view).
* ``w`` \u2014 enter the Whiteboards module (pushes the whiteboard picker
  on top of the tasks view).
* ``j`` / ``k`` / arrows \u2014 move highlight.
* ``enter`` \u2014 activate highlighted module.
* ``q`` \u2014 quit the whole app.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

# Stable identifiers used as list_view item ids.
MODULE_TASKS = "tasks"
MODULE_WHITEBOARDS = "whiteboards"


class ModulePickerScreen(Screen[None]):
    """Landing screen presenting the available modules."""

    BLANK = True  # children render their own backgrounds

    DEFAULT_CSS = """
    ModulePickerScreen {
        align: center middle;
    }
    #picker {
        width: 50;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $accent;
    }
    #picker Label.title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }
    #picker #hint {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("t", "pick('tasks')", "[t]asks"),
        Binding("w", "pick('whiteboards')", "[w]hiteboards"),
        Binding("enter", "activate", "open", show=False),
        Binding("j", "cursor_down", "\u2193", show=False),
        Binding("k", "cursor_up", "\u2191", show=False),
        Binding("q", "quit_app", "[q]uit"),
    ]

    # The list of modules rendered top-to-bottom. ``key`` is matched
    # against the string arg passed to ``action_pick``.
    MODULES: list[tuple[str, str, str]] = [
        (MODULE_TASKS, "Tasks", "tasks and projects"),
        (MODULE_WHITEBOARDS, "Whiteboards", "free-form boxes & connectors"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="picker"):
            yield Label("systema2 \u2014 pick a module", classes="title")
            yield ListView(id="modules")
            yield Static(
                "[t] tasks  \u2022  [w] whiteboards  \u2022  [\u21b5] open  \u2022  [q] quit",
                id="hint",
            )
        yield Footer()

    def on_mount(self) -> None:
        lv = self.query_one(ListView)
        for key, name, blurb in self.MODULES:
            item = ListItem(Label(f"{name}  \u2014  {blurb}"))
            item.id = f"mod-{key}"
            lv.append(item)
        lv.index = 0
        lv.focus()

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def action_activate(self) -> None:
        lv = self.query_one(ListView)
        i = lv.index
        if i is None or not (0 <= i < len(self.MODULES)):
            return
        key = self.MODULES[i][0]
        self.action_pick(key)

    def action_pick(self, key: str) -> None:
        """Dispatch to the app's module-entry hook, then dismiss."""
        app = self.app
        hook = getattr(app, "enter_module", None)
        if hook is not None:
            hook(key)
        self.app.pop_screen()

    def action_quit_app(self) -> None:
        self.app.exit()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Double-click / enter on a row \u2192 activate it.
        self.action_activate()
