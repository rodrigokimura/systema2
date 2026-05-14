"""Calendar module for the TUI.

A monthly calendar view with a sidebar for switching between
monthly / weekly / yearly views. Days are rendered as larger cells
with tasks due on that day.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.visual import Visual
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from systema2.models import Task
from systema2.repository import RepositoryError, TaskRepository

# Sidebar view keys
_VIEW_MONTHLY = "monthly"
_VIEW_WEEKLY = "weekly"
_VIEW_YEARLY = "yearly"
_VIEW_DAILY = "daily"

# ---------------------------------------------------------------------------
# Grid drawing helpers
# ---------------------------------------------------------------------------


def _box_line(left: str, mid: str, right: str, col_width: int, n_cols: int = 7) -> str:
    cell = "─" * col_width
    return left + mid.join([cell] * n_cols) + right


def _month_grid_text(
    year: int,
    month: int,
    today: date | None,
    width: int,
    tasks_by_day: dict[date, list[Task]],
    *,
    cell_height: int = 4,
) -> Text:
    """Monthly calendar with larger cells showing tasks per day."""
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    weeks = cal.monthdayscalendar(year, month)
    col_width = max(6, (width - 8) // 7)
    n_cols = 7
    max_tasks = cell_height - 2  # rows available for tasks (day number + overflow)

    C = {
        "tl": "┌",
        "tm": "┬",
        "tr": "┐",
        "ml": "├",
        "mm": "┼",
        "mr": "┤",
        "bl": "└",
        "bm": "┴",
        "br": "┘",
        "v": "│",
    }

    def _border(left: str, mid: str, right: str) -> str:
        return _box_line(left, mid, right, col_width, n_cols)

    result = Text()

    # Top border
    result.append(_border(C["tl"], C["tm"], C["tr"]) + "\n")

    # Day names header
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    result.append(C["v"])
    for name in day_names:
        result.append(f"{name:^{col_width}}")
        result.append(C["v"])
    result.append("\n")

    # Separator under header
    result.append(_border(C["ml"], C["mm"], C["mr"]) + "\n")

    for wi, week in enumerate(weeks):
        for row in range(cell_height):
            result.append(C["v"])
            for day in week:
                if day == 0:
                    result.append(" " * col_width)
                else:
                    d = date(year, month, day)
                    day_tasks = tasks_by_day.get(d, [])

                    if row == 0:
                        mark = f" {day}".ljust(col_width)
                        style = "bold yellow on magenta" if today == d else "bold"
                        result.append(mark, style=style)
                    elif 1 <= row <= max_tasks:
                        idx = row - 1
                        if idx < len(day_tasks):
                            t = day_tasks[idx]
                            prefix = "✓ " if t.completed else "· "
                            text = (prefix + t.title)[: col_width - 1].ljust(col_width)
                            pri_style = {
                                "H": "bold red",
                                "M": "bold yellow",
                                "L": "dim",
                            }.get(t.priority.value, "")
                            if t.completed:
                                pri_style = "dim strike"
                            result.append(text, style=pri_style)
                        elif idx == max_tasks and len(day_tasks) > max_tasks:
                            overflow = len(day_tasks) - max_tasks
                            text = f" +{overflow} more".ljust(col_width)
                            result.append(text, style="dim")
                        else:
                            result.append(" " * col_width)
                    else:
                        result.append(" " * col_width)
                result.append(C["v"])
            result.append("\n")

        if wi == len(weeks) - 1:
            result.append(_border(C["bl"], C["bm"], C["br"]) + "\n")
        else:
            result.append(_border(C["ml"], C["mm"], C["mr"]) + "\n")

    return result


def _year_grid_text(
    year: int,
    today: date | None,
    width: int,
    tasks_by_day: dict[date, list[Task]],
) -> Text:
    """Compact yearly grid (3×4 months) with task indicators."""
    col_inner = max(18, (width - 4) // 3)
    result = Text()
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)

    for row_start in range(0, 12, 3):
        months = [row_start + 1, row_start + 2, row_start + 3]

        # Month headers
        for m in months:
            result.append(f" {calendar.month_name[m][:3]}".ljust(col_inner), style="bold cyan")
        result.append("\n")

        # Day labels
        for _ in months:
            result.append(" Mo Tu We Th Fr Sa Su ".ljust(col_inner))
        result.append("\n")

        max_weeks = max(len(cal.monthdayscalendar(year, m)) for m in months)

        for wi in range(max_weeks):
            for m in months:
                weeks = cal.monthdayscalendar(year, m)
                if wi < len(weeks):
                    week = weeks[wi]
                    cells: list[str] = []
                    for day in week:
                        if day == 0:
                            cells.append("  ")
                        else:
                            mark = f"{day:2d}"
                            d = date(year, m, day)
                            if today and today == d:
                                mark = f"[{mark}]"
                            elif d in tasks_by_day:
                                mark = f"*{mark.lstrip()}"
                            cells.append(mark)
                    row_text = " " + " ".join(cells)
                else:
                    row_text = ""
                result.append(row_text.ljust(col_inner))
            result.append("\n")

        result.append("\n")

    return result


def _week_grid_text(
    ref: date,
    today: date | None,
    width: int,
    tasks_by_day: dict[date, list[Task]],
    *,
    cell_height: int = 6,
) -> Text:
    """Weekly view showing tasks for the 7 days."""
    monday = ref - timedelta(days=ref.weekday())
    col_width = max(10, (width - 8) // 7)
    n_cols = 7
    max_tasks = cell_height - 2

    C = {
        "tl": "┌",
        "tm": "┬",
        "tr": "┐",
        "ml": "├",
        "mm": "┼",
        "mr": "┤",
        "bl": "└",
        "bm": "┴",
        "br": "┘",
        "v": "│",
    }

    def _border(left: str, mid: str, right: str) -> str:
        return _box_line(left, mid, right, col_width, n_cols)

    result = Text()
    result.append(_border(C["tl"], C["tm"], C["tr"]) + "\n")

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    result.append(C["v"])
    for name in day_names:
        result.append(f"{name:^{col_width}}")
        result.append(C["v"])
    result.append("\n")
    result.append(_border(C["ml"], C["mm"], C["mr"]) + "\n")

    for row in range(cell_height):
        result.append(C["v"])
        for i in range(7):
            d = monday + timedelta(days=i)
            day_tasks = tasks_by_day.get(d, [])
            if row == 0:
                mark = f" {d.day}".ljust(col_width)
                style = "bold yellow on magenta" if today == d else "bold"
                result.append(mark, style=style)
            elif 1 <= row <= max_tasks:
                idx = row - 1
                if idx < len(day_tasks):
                    t = day_tasks[idx]
                    prefix = "✓ " if t.completed else "· "
                    text = (prefix + t.title)[: col_width - 1].ljust(col_width)
                    pri_style = {
                        "H": "bold red",
                        "M": "bold yellow",
                        "L": "dim",
                    }.get(t.priority.value, "")
                    if t.completed:
                        pri_style = "dim strike"
                    result.append(text, style=pri_style)
                elif idx == max_tasks and len(day_tasks) > max_tasks:
                    text = f" +{len(day_tasks) - max_tasks} more".ljust(col_width)
                    result.append(text, style="dim")
                else:
                    result.append(" " * col_width)
            else:
                result.append(" " * col_width)
            result.append(C["v"])
        result.append("\n")

    result.append(_border(C["bl"], C["bm"], C["br"]) + "\n")
    return result


def _day_detail_text(
    ref: date,
    today: date | None,
    width: int,
    tasks: list[Task],
) -> Text:
    """Single day view with full task list."""
    header = f" {ref.strftime('%A  %d %B %Y')} "
    if ref == today:
        header = f" [{ref.strftime('%A  %d %B %Y')}] "
    header = header.center(width, "=")
    result = Text(header + "\n")
    if not tasks:
        result.append("  No tasks due.\n")
        return result
    for t in tasks:
        prefix = "✓ " if t.completed else "· "
        pri = f"[{t.priority.value}]"
        text = f"  {prefix}{pri}  {t.title}\n"
        pri_style = {
            "H": "bold red",
            "M": "bold yellow",
            "L": "dim",
        }.get(t.priority.value, "")
        if t.completed:
            pri_style = "dim strike"
        result.append(text, style=pri_style)
    return result


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
        width = self.size.width or 80
        tasks_by_day = screen._tasks_by_day

        if view == _VIEW_MONTHLY:
            return _month_grid_text(ref.year, ref.month, today, width, tasks_by_day)
        if view == _VIEW_WEEKLY:
            return _week_grid_text(ref, today, width, tasks_by_day)
        if view == _VIEW_YEARLY:
            return _year_grid_text(ref.year, today, width, tasks_by_day)
        if view == _VIEW_DAILY:
            return _day_detail_text(ref, today, width, tasks_by_day.get(ref, []))
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
    #calendar_body {
        height: auto;
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

    def __init__(self, repo: TaskRepository | None = None) -> None:
        super().__init__()
        self._repo = repo
        self._today = date.today()
        self._ref = self._today
        self._view = _VIEW_MONTHLY
        self._tasks_by_day: dict[date, list[Task]] = {}

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
            with ScrollableContainer(id="calendar_main"):
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
        self._update()

    def _load_tasks(self) -> None:
        self._tasks_by_day = {}
        if self._repo is None:
            return

        if self._view == _VIEW_MONTHLY:
            start = self._ref.replace(day=1)
            nxt = start + timedelta(days=32)
            end = nxt.replace(day=1) - timedelta(days=1)
        elif self._view == _VIEW_WEEKLY:
            start = self._ref - timedelta(days=self._ref.weekday())
            end = start + timedelta(days=6)
        elif self._view == _VIEW_DAILY:
            start = end = self._ref
        elif self._view == _VIEW_YEARLY:
            start = self._ref.replace(month=1, day=1)
            end = self._ref.replace(month=12, day=31)
        else:
            return

        try:
            all_tasks = self._repo.list_tasks()
        except RepositoryError:
            return

        for t in all_tasks:
            if t.due_date and start <= t.due_date <= end:
                self._tasks_by_day.setdefault(t.due_date, []).append(t)

        for ts in self._tasks_by_day.values():
            ts.sort(
                key=lambda t: (
                    t.completed,
                    {"H": 0, "M": 1, "L": 2}.get(t.priority.value, 1),
                    t.title,
                )
            )

    def _update_header(self) -> None:
        header = self.query_one("#calendar_header", Static)
        if self._view == _VIEW_MONTHLY:
            header.update(self._ref.strftime("%B %Y"))
        elif self._view == _VIEW_WEEKLY:
            monday = self._ref - timedelta(days=self._ref.weekday())
            sunday = monday + timedelta(days=6)
            header.update(
                f"Week {monday.strftime('%d %b')} \u2013 {sunday.strftime('%d %b %Y')}"
            )
        elif self._view == _VIEW_YEARLY:
            header.update(str(self._ref.year))
        elif self._view == _VIEW_DAILY:
            header.update(self._ref.strftime("%A %d %B %Y"))

    def _update(self) -> None:
        self._load_tasks()
        self._update_header()
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
        self._update()

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
        self._update()

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
        self._update()

    def action_cursor_down(self) -> None:
        self.query_one("#view_list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#view_list", ListView).action_cursor_up()
