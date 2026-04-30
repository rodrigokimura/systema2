"""Whiteboard picker screen.

Lists existing whiteboards and lets the user pick one to open, create a
new one, or delete one. Designed to be pushed on top of the main
systema2 app via ``self.push_screen(WhiteboardListScreen())``.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, ListItem, ListView, Label, Static

from systema2 import whiteboard_services as wbs
from systema2.models import Whiteboard, WhiteboardCreate
from systema2.tui.screens.whiteboard import WhiteboardScreen


class WhiteboardListScreen(Screen[None]):
    """Pick / create / delete whiteboards."""

    DEFAULT_CSS = """
    WhiteboardListScreen {
        align: center middle;
    }
    #box {
        width: 60%;
        height: 80%;
        padding: 1 2;
        background: $surface;
        border: thick $accent;
    }
    #box Label.title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }
    #box #hint {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "back"),
        Binding("q", "close", "back"),
        Binding("enter", "open_selected", "open"),
        Binding("n", "new", "[n]ew board"),
        Binding("x", "delete", "[x] delete"),
        Binding("j", "cursor_down", "\u2193", show=False),
        Binding("k", "cursor_up", "\u2191", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._whiteboards: list[Whiteboard] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="box"):
            yield Label("Whiteboards", classes="title")
            yield ListView(id="wb_list")
            yield Static(
                "[enter] open  \u2022  [n] new  \u2022  [x] delete  \u2022  [q/esc] back",
                id="hint",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._reload()
        self.query_one(ListView).focus()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _reload(self) -> None:
        self._whiteboards = wbs.list_whiteboards_std()
        lv = self.query_one(ListView)
        # clear() is async; schedule a follow-up append via call_later.
        prev = lv.index
        lv.clear()
        for wb in self._whiteboards:
            lv.append(ListItem(Label(f"#{wb.id}  {wb.name}")))
        if self._whiteboards:
            lv.index = 0 if prev is None else min(prev, len(self._whiteboards) - 1)

    def _selected(self) -> Whiteboard | None:
        lv = self.query_one(ListView)
        i = lv.index
        if i is None or not (0 <= i < len(self._whiteboards)):
            return None
        return self._whiteboards[i]

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def action_new(self) -> None:
        n = len(self._whiteboards) + 1
        wb = wbs.create_whiteboard_std(
            WhiteboardCreate(name=f"whiteboard {n}")
        )
        self._reload()
        self.app.push_screen(WhiteboardScreen(wb))

    def action_delete(self) -> None:
        wb = self._selected()
        if wb is None or wb.id is None:
            return
        wbs.delete_whiteboard_std(wb.id)
        self._reload()

    def action_open_selected(self) -> None:
        wb = self._selected()
        if wb is None:
            return
        self.app.push_screen(WhiteboardScreen(wb))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Double-click / enter on a row → open it.
        self.action_open_selected()
