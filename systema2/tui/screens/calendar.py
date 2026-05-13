"""Calendar module for the TUI.

A monthly calendar view with a sidebar for switching between
monthly / weekly / yearly views (views beyond monthly are visual
stubs for now).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.visual import Visual
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

# Sidebar view keys
_VIEW_MONTHLY = "monthly"
_VIEW_WEEKLY = "weekly"
_VIEW_YEARLY = "yearly"
_VIEW_DAILY = "daily"

# ---------------------------------------------------------------------------
# Month table helpers
# ---------------------------------------------------------------------------

def _month_grid(year: int, month: int, today: date | None = None) -> Text:
    """Build a monospace string grid for a single month."""
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    weeks = cal.monthdayscalendar(year, month)
    lines: list[str] = ["  Mon  Tue  Wed  Thu  Fri  Sat  Sun  "]
    for week in weeks:
        cells: list[str] = []
        for day in week:
            if day == 0:
                cells.append("     ")
            else:
                mark = f"{day:>4d} "
                if today is not None and today.year == year and today.month == month and today.day == day:
                    cells.append(f"[{mark.rstrip()}]")
                else:
                    cells.append(mark)
        lines.append("".join(cells))
    return Text("\n".join(lines))


def _year_grid(year: int, today: date | None = None) -> Text:
    """Build a compact yearly grid (3×4 months)."""
    lines: list[str] = []
    for row_start in range(0, 12, 3):
        months: list[list[str]] = []
        for m in range(row_start + 1, row_start + 4):
            cal = calendar.Calendar(firstweekday=calendar.MONDAY)
            weeks = cal.monthdayscalendar(year, m)
            month_lines: list[str] = [calendar.month_name[m][:3]]
            month_lines.append("Mo Tu We Th Fr Sa Su")
            for week in weeks:
                cells: list[str] = []
                for day in week:
                    if day == 0:
                        cells.append("  ")
                    else:
                        mark = f"{day:2d}"
                        if today and today.year == year and today.month == m and today.day == day:
                            cells.append(f"[{mark}]")
                        else:
                            cells.append(mark)
                month_lines.append(" ".join(cells))
            while len(month_lines) < 8:
                month_lines.append("")
            months.append(month_lines)
        # Join three month columns side by side
        for row_idx in range(8):
            parts: list[str] = []
            for month_lines in months:
                parts.append(month_lines[row_idx].ljust(22))
            lines.append("  ".join(parts))
        lines.append("")
    return Text("\n".join(lines))


def _week_grid(ref: date, today: date | None = None) -> Text:
    """Build a weekly view for the ISO week containing *ref*."""
    monday = ref - timedelta(days=ref.weekday())
    lines: list[str] = ["  Mon  Tue  Wed  Thu  Fri  Sat  Sun  "]
    cells: list[str] = []
    for i in range(7):
        d = monday + timedelta(days=i)
        mark = f"{d.day:>4d} "
        if today == d:
            mark = f"[{mark.rstrip()}]"
        cells.append(mark.ljust(5))
    lines.append("".join(cells))
    return Text("\n".join(lines))


def _day_header(ref: date, today: date | None = None) -> Text:
    """A simple single-day view."""
    text = ref.strftime("%A  %d %B %Y")
    if ref == today:
        text = f"[{text}]"
    return Text(text)


# ---------------------------------------------------------------------------
# Calendar body widget
# ---------------------------------------------------------------------------

class CalendarBody(Static):
    """Custom widget that renders the calendar grid as a Textual Visual."""

    def __init__(self, *, screen: "CalendarScreen", **kwargs) -> None:
        super().__init__(**kwargs)
        self._calendar_screen = screen

    def render(self) -> Visual:
        screen = self._calendar_screen
        view = screen._view
        ref = screen._ref
        today = screen._today

        if view == _VIEW_MONTHLY:
            return _month_grid(ref.year, ref.month, today)
        if view == _VIEW_WEEKLY:
            return _week_grid(ref, today)
        if view == _VIEW_YEARLY:
            return _year_grid(ref.year, today)
        if view == _VIEW_DAILY:
            return _day_header(ref, today)
        return Text("")


# ---------------------------------------------------------------------------
# Calendar screen
# ---------------------------------------------------------------------------

class CalendarScreen(Screen[None]):
    """Calendar viewer with a sidebar for view-mode switching."""

    DEFAULT_CSS = """
    CalendarScreen {
        height: 1fr;
    }
    #calendar_sidebar {
        width: 18;
        border-right: solid $accent;
        background: $surface;
    }
    #calendar_sidebar ListView {
        height: auto;
    }
    #calendar_sidebar .section {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        padding-top: 1;
    }
    #calendar_main {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    #calendar_header {
        height: auto;
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "back"),
        Binding("q", "close", "back"),
        Binding("h", "prev", "\u2190 prev"),
        Binding("l", "next", "\u2192 next"),
        Binding("j", "cursor_down", "\u2193", show=False),
        Binding("k", "cursor_up", "\u2191", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._today = date.today()
        self._ref = self._today  # the month/week/day currently displayed
        self._view = _VIEW_MONTHLY

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="calendar_sidebar"):
                yield Label("Views", classes="section")
                yield ListView(
                    ListItem(Label("Monthly")),
                    ListItem(Label("Weekly")),
                    ListItem(Label("Yearly")),
                    ListItem(Label("Daily")),
                    id="view_list",
                )
            with Vertical(id="calendar_main"):
                yield Static(" ", id="calendar_header")
                yield CalendarBody(screen=self, id="calendar_body")
        yield Footer()

    def on_mount(self) -> None:
        lv = self.query_one("#view_list", ListView)
        index_map = {
            _VIEW_MONTHLY: 0,
            _VIEW_WEEKLY: 1,
            _VIEW_YEARLY: 2,
            _VIEW_DAILY: 3,
        }
        lv.index = index_map.get(self._view, 0)
        lv.focus()
        self._update_header()

    def _update_header(self) -> None:
        header = self.query_one("#calendar_header", Static)
        if self._view == _VIEW_MONTHLY:
            header.update(self._ref.strftime("%B %Y"))
        elif self._view == _VIEW_WEEKLY:
            monday = self._ref - timedelta(days=self._ref.weekday())
            sunday = monday + timedelta(days=6)
            header.update(f"Week {monday.strftime('%d %b')} \u2013 {sunday.strftime('%d %b %Y')}")
        elif self._view == _VIEW_YEARLY:
            header.update(str(self._ref.year))
        elif self._view == _VIEW_DAILY:
            header.update(self._ref.strftime("%A %d %B %Y"))
        body = self.query_one("#calendar_body", CalendarBody)
        body.refresh()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        view_map = {
            0: _VIEW_MONTHLY,
            1: _VIEW_WEEKLY,
            2: _VIEW_YEARLY,
            3: _VIEW_DAILY,
        }
        self._view = view_map.get(idx, _VIEW_MONTHLY)
        self._update_header()

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_prev(self) -> None:
        if self._view == _VIEW_MONTHLY:
            year = self._ref.year if self._ref.month > 1 else self._ref.year - 1
            month = self._ref.month - 1 if self._ref.month > 1 else 12
            self._ref = self._ref.replace(year=year, month=month)
        elif self._view == _VIEW_WEEKLY:
            self._ref -= timedelta(weeks=1)
        elif self._view == _VIEW_YEARLY:
            self._ref = self._ref.replace(year=self._ref.year - 1)
        elif self._view == _VIEW_DAILY:
            self._ref -= timedelta(days=1)
        self._update_header()

    def action_next(self) -> None:
        if self._view == _VIEW_MONTHLY:
            year = self._ref.year if self._ref.month < 12 else self._ref.year + 1
            month = self._ref.month + 1 if self._ref.month < 12 else 1
            self._ref = self._ref.replace(year=year, month=month)
        elif self._view == _VIEW_WEEKLY:
            self._ref += timedelta(weeks=1)
        elif self._view == _VIEW_YEARLY:
            self._ref = self._ref.replace(year=self._ref.year + 1)
        elif self._view == _VIEW_DAILY:
            self._ref += timedelta(days=1)
        self._update_header()

    def action_cursor_down(self) -> None:
        self.query_one("#view_list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#view_list", ListView).action_cursor_up()
