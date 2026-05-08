"""Textual whiteboard screen: canvas with boxes and auto-rendered connectors.

The canvas is a fixed-size character grid rendered into a single
``Static`` widget. Boxes are drawn with Unicode box-drawing characters
(\u250c \u2500 \u2510 \u2502 \u2514 \u2518) and connectors are drawn as orthogonal S-shaped
poly-lines between the centres of their source and target boxes, with
an arrowhead at the target end. S-shapes have two 90° bends (at a
shared midpoint) so the dogleg stays clear of the boxes instead of
hugging them like an L. Boxes on the same row or column degenerate to
a straight line.

The widget is intentionally self-contained \u2014 it takes the current set
of boxes and connectors and produces a Rich ``Text`` each render pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Select, Static

from systema2 import whiteboard_services as wbs
from systema2.models import (
    Box,
    BoxCreate,
    BoxUpdate,
    Connector,
    ConnectorCreate,
    Whiteboard,
)
from systema2.tui.screens.rename_box import RenameBoxScreen


# ---------------------------------------------------------------------------
# Canvas rendering
# ---------------------------------------------------------------------------


CANVAS_WIDTH = 120
CANVAS_HEIGHT = 40

# Terminal characters are roughly twice as tall as they are wide.
# We compensate for this in distance calculations so that a 1-cell
# vertical gap feels visually equivalent to a 2-cell horizontal gap.
_ASPECT = 2.0

# Minimum padding around the furthest renderable so the canvas doesn't
# feel cramped at the edges.
_CANVAS_PAD = 2

# Toolbar style options
_BORDER_OPTIONS: list[tuple[str, str]] = [
    ("white", "bold white"),
    ("red", "bold red"),
    ("green", "bold green"),
    ("blue", "bold blue"),
    ("magenta", "bold magenta"),
    ("cyan", "bold cyan"),
    ("dim", "dim white"),
]
_FILL_OPTIONS: list[tuple[str, str | None]] = [
    ("(none)", ""),
    ("white bg", "on white"),
    ("red bg", "on red"),
    ("green bg", "on green"),
    ("blue bg", "on blue"),
    ("magenta bg", "on magenta"),
    ("cyan bg", "on cyan"),
    ("yellow bg", "on yellow"),
]


@dataclass(frozen=True)
class _RenderedBox:
    box_id: str
    left: int
    top: int
    right: int  # inclusive
    bottom: int  # inclusive

    @property
    def center_x(self) -> int:
        return (self.left + self.right) // 2

    @property
    def center_y(self) -> int:
        return (self.top + self.bottom) // 2


def _required_canvas_size(
    boxes: Iterable[Box],
) -> tuple[int, int]:
    """Return the (width, height) needed to fit every box + padding.

    If there are no boxes the fixed default size is returned so the
    screen still shows a blank canvas that can be panned later."""
    all_boxes = list(boxes)
    if not all_boxes:
        return CANVAS_WIDTH, CANVAS_HEIGHT
    max_right = max(b.x + b.width for b in all_boxes)
    max_bottom = max(b.y + b.height for b in all_boxes)
    w = max(CANVAS_WIDTH, max_right + _CANVAS_PAD)
    h = max(CANVAS_HEIGHT, max_bottom + _CANVAS_PAD)
    return w, h


def render_canvas(
    boxes: Iterable[Box],
    connectors: Iterable[Connector],
    *,
    selected_box_id: str | None = None,
) -> Text:
    """Render the whiteboard into a Rich ``Text`` grid.

    The canvas size is computed from the bounding box of all
    renderables plus a small padding, so the board auto-expands as
    boxes are moved outward. Connectors are drawn first so boxes
    overwrite their endpoints, which keeps the box outlines clean.
    """
    width, height = _required_canvas_size(boxes)

    grid = [[" "] * width for _ in range(height)]
    styles: list[list[str | None]] = [[None] * width for _ in range(height)]

    rendered: dict[str, _RenderedBox] = {}
    for b in boxes:
        assert b.id is not None
        left = b.x
        top = b.y
        right = left + b.width - 1
        bottom = top + b.height - 1
        rendered[b.id] = _RenderedBox(b.id, left, top, right, bottom)

    # 1) Connectors first so boxes overwrite their endpoints.
    for c in connectors:
        src = rendered.get(c.source_box_id)
        dst = rendered.get(c.target_box_id)
        if src is None or dst is None:
            continue
        _draw_connector(grid, styles, src, dst)

    # 2) Boxes on top.
    for b in boxes:
        assert b.id is not None
        r = rendered[b.id]
        is_selected = selected_box_id is not None and b.id == selected_box_id
        border_style = (
            "bold yellow" if is_selected else (b.border_style or "bold white")
        )
        fill_style = b.fill_style
        _draw_box(grid, styles, r, b.label, border_style, fill_style)

    # Join into a Rich Text with per-character style hints.
    out = Text()
    for row_idx, row in enumerate(grid):
        for col_idx, ch in enumerate(row):
            out.append(ch, style=styles[row_idx][col_idx] or "")
        out.append("\n")
    return out


def _set(
    grid: list[list[str]],
    styles: list[list[str | None]],
    x: int,
    y: int,
    ch: str,
    style: str | None,
) -> None:
    if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
        grid[y][x] = ch
        styles[y][x] = style


def _draw_box(
    grid: list[list[str]],
    styles: list[list[str | None]],
    r: _RenderedBox,
    label: str,
    border_style: str,
    fill_style: str | None = None,
) -> None:
    # Corners
    _set(grid, styles, r.left, r.top, "\u250c", border_style)
    _set(grid, styles, r.right, r.top, "\u2510", border_style)
    _set(grid, styles, r.left, r.bottom, "\u2514", border_style)
    _set(grid, styles, r.right, r.bottom, "\u2518", border_style)
    # Horizontal edges
    for x in range(r.left + 1, r.right):
        _set(grid, styles, x, r.top, "\u2500", border_style)
        _set(grid, styles, x, r.bottom, "\u2500", border_style)
    # Vertical edges
    for y in range(r.top + 1, r.bottom):
        _set(grid, styles, r.left, y, "\u2502", border_style)
        _set(grid, styles, r.right, y, "\u2502", border_style)
    # Fill interior (or clear if no fill specified).
    for y in range(r.top + 1, r.bottom):
        for x in range(r.left + 1, r.right):
            _set(grid, styles, x, y, " ", fill_style)
    # Label (truncated to fit).
    inner_width = r.right - r.left - 1
    if inner_width > 0:
        text = label[:inner_width]
        row = (r.top + r.bottom) // 2
        start = r.left + 1 + max(0, (inner_width - len(text)) // 2)
        for i, ch in enumerate(text):
            _set(grid, styles, start + i, row, ch, border_style)


def _draw_hline(
    grid: list[list[str]],
    styles: list[list[str | None]],
    x0: int,
    x1: int,
    y: int,
    style: str,
) -> None:
    """Draw a horizontal run (inclusive on both ends), skipping non-blank cells."""
    lo, hi = sorted((x0, x1))
    for x in range(lo, hi + 1):
        if 0 <= y < len(grid) and 0 <= x < len(grid[0]) and grid[y][x] == " ":
            _set(grid, styles, x, y, "\u2500", style)


def _draw_vline(
    grid: list[list[str]],
    styles: list[list[str | None]],
    x: int,
    y0: int,
    y1: int,
    style: str,
) -> None:
    """Draw a vertical run (inclusive on both ends), skipping non-blank cells."""
    lo, hi = sorted((y0, y1))
    for y in range(lo, hi + 1):
        if 0 <= y < len(grid) and 0 <= x < len(grid[0]) and grid[y][x] == " ":
            _set(grid, styles, x, y, "\u2502", style)


def _draw_connector(
    grid: list[list[str]],
    styles: list[list[str | None]],
    src: _RenderedBox,
    dst: _RenderedBox,
) -> None:
    """Route an S-shaped orthogonal line from ``src`` to ``dst``.

    An S-shape has two 90° turns so the dogleg bends gracefully around
    the midpoint instead of hugging the target like an L. Three flavours:

    * **horizontal S** (boxes to the left/right of each other): exit
      the source horizontally, turn at the midpoint x, run vertically
      to the target row, turn again, and arrive horizontally.
    * **vertical S** (boxes above/below each other): exit the source
      vertically, turn at the midpoint y, run horizontally to the
      target column, turn again, and arrive vertically.
    * **straight** (boxes exactly aligned on a row or column): a plain
      line with no turns — the degenerate case.
    """
    style = "cyan"

    # ---- Straight (degenerate) cases ---------------------------------
    # Same centre row → pure horizontal line. Same centre column → pure
    # vertical line. We keep these as-is because they render cleanly and
    # the existing tests assert on the straight-line shape.
    if src.center_y == dst.center_y and src.center_x != dst.center_x:
        if dst.center_x > src.center_x:
            sx, tx = src.right + 1, dst.left - 1
            arrow = "\u25b6"
        else:
            sx, tx = src.left - 1, dst.right + 1
            arrow = "\u25c0"
        y = src.center_y
        _draw_hline(grid, styles, sx, tx, y, style)
        _set(grid, styles, tx, y, arrow, style)
        return

    if src.center_x == dst.center_x and src.center_y != dst.center_y:
        if dst.center_y > src.center_y:
            sy, ty = src.bottom + 1, dst.top - 1
            arrow = "\u25bc"
        else:
            sy, ty = src.top - 1, dst.bottom + 1
            arrow = "\u25b2"
        x = src.center_x
        _draw_vline(grid, styles, x, sy, ty, style)
        _set(grid, styles, x, ty, arrow, style)
        return

    # ---- General S-shapes --------------------------------------------
    # Pick the dominant axis by which separation is larger. When the
    # horizontal gap dominates we use a horizontal S (enter/exit from
    # the sides); when the vertical gap dominates we use a vertical S
    # (enter/exit top/bottom).
    horizontal_gap = abs(dst.center_x - src.center_x)
    vertical_gap = abs(dst.center_y - src.center_y)

    if horizontal_gap >= vertical_gap:
        # Horizontal S.
        going_right = dst.center_x > src.center_x
        going_down = dst.center_y > src.center_y
        if going_right:
            sx = src.right + 1
            tx = dst.left - 1
            arrow = "\u25b6"
        else:
            sx = src.left - 1
            tx = dst.right + 1
            arrow = "\u25c0"
        sy, ty = src.center_y, dst.center_y
        mx = (sx + tx) // 2  # midpoint column where the dogleg happens

        # First horizontal leg: source edge -> midpoint.
        _draw_hline(grid, styles, sx, mx, sy, style)
        # Vertical leg at mx between the two rows.
        _draw_vline(grid, styles, mx, sy, ty, style)
        # Second horizontal leg: midpoint -> target edge.
        _draw_hline(grid, styles, mx, tx, ty, style)

        # Corner glyphs at the two bends. The horizontal pieces already
        # wrote "\u2500" at (mx, sy) and (mx, ty); overwrite with bends.
        if going_right and going_down:
            _set(grid, styles, mx, sy, "\u2510", style)  # ┐
            _set(grid, styles, mx, ty, "\u2514", style)  # └
        elif going_right and not going_down:
            _set(grid, styles, mx, sy, "\u2518", style)  # ┘
            _set(grid, styles, mx, ty, "\u250c", style)  # ┌
        elif not going_right and going_down:
            _set(grid, styles, mx, sy, "\u250c", style)  # ┌
            _set(grid, styles, mx, ty, "\u2518", style)  # ┘
        else:  # left and up
            _set(grid, styles, mx, sy, "\u2514", style)  # └
            _set(grid, styles, mx, ty, "\u2510", style)  # ┐

        _set(grid, styles, tx, ty, arrow, style)
        return

    # Vertical S.
    going_down = dst.center_y > src.center_y
    going_right = dst.center_x > src.center_x
    if going_down:
        sy = src.bottom + 1
        ty = dst.top - 1
        arrow = "\u25bc"
    else:
        sy = src.top - 1
        ty = dst.bottom + 1
        arrow = "\u25b2"
    sx, tx = src.center_x, dst.center_x
    my = (sy + ty) // 2  # midpoint row where the dogleg happens

    # First vertical leg: source edge -> midpoint row.
    _draw_vline(grid, styles, sx, sy, my, style)
    # Horizontal leg at my between the two columns.
    _draw_hline(grid, styles, sx, tx, my, style)
    # Second vertical leg: midpoint row -> target edge.
    _draw_vline(grid, styles, tx, my, ty, style)

    if going_down and going_right:
        _set(grid, styles, sx, my, "\u2514", style)  # └
        _set(grid, styles, tx, my, "\u2510", style)  # ┐
    elif going_down and not going_right:
        _set(grid, styles, sx, my, "\u2518", style)  # ┘
        _set(grid, styles, tx, my, "\u250c", style)  # ┌
    elif not going_down and going_right:
        _set(grid, styles, sx, my, "\u250c", style)  # ┌
        _set(grid, styles, tx, my, "\u2518", style)  # ┘
    else:  # up and left
        _set(grid, styles, sx, my, "\u2510", style)  # ┐
        _set(grid, styles, tx, my, "\u2514", style)  # └

    _set(grid, styles, tx, ty, arrow, style)


# ---------------------------------------------------------------------------
# Canvas widget (draggable scrolling)
# ---------------------------------------------------------------------------

class _Canvas(Static):
    """Canvas widget that captures mouse drag to pan the parent scroll container."""

    FOCUS_ON_CLICK = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._drag_start: Offset | None = None
        self._scroll_start: tuple[float, float] = (0, 0)
        self._click_delta: Offset | None = None

    def _screen(self) -> WhiteboardScreen | None:
        s = self.screen
        if isinstance(s, WhiteboardScreen):
            return s
        return None

    def _container(self) -> ScrollableContainer | None:
        p = self.parent
        if isinstance(p, ScrollableContainer):
            return p
        return None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if self._container() is None:
            return
        self.capture_mouse()
        self._drag_start = event.screen_offset
        self._click_delta = Offset(0, 0)
        self._scroll_start = (self._container().scroll_x, self._container().scroll_y)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self.release_mouse()
        # Only treat as a click if we didn't drag significantly.
        if (
            self._click_delta is not None
            and abs(self._click_delta.x) <= 1
            and abs(self._click_delta.y) <= 1
        ):
            screen = self._screen()
            if screen is not None:
                screen._handle_canvas_click(event.offset)
        self._drag_start = None
        self._click_delta = None

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag_start is None:
            return
        if self._click_delta is not None:
            self._click_delta = Offset(
                event.screen_offset.x - self._drag_start.x,
                event.screen_offset.y - self._drag_start.y,
            )
        container = self._container()
        if container is None:
            return
        dx = event.screen_offset.x - self._drag_start.x
        dy = event.screen_offset.y - self._drag_start.y
        # Invert delta: dragging up/right should reveal content
        # below/left, just like we pan a map.
        container.scroll_to(
            self._scroll_start[0] - dx,
            self._scroll_start[1] - dy,
            animate=False,
        )


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------


_STATUS_CSS = """
#canvas_scroll {
    height: 1fr;
    width: 1fr;
    padding: 0 1;
    overflow-x: auto;
    overflow-y: auto;
}
#canvas {
    width: auto;
    height: auto;
}
#status {
    dock: bottom;
    height: 1;
    padding: 0 1;
    background: $panel;
}
/* Floating toolbar – docked on the right edge, vertically centred */
#style_toolbar {
    dock: right;
    layer: toolbar;
    width: 18;
    height: auto;
    background: $surface;
    border: solid $accent;
    padding: 1 0;
    display: none;
}
#style_toolbar Button {
    width: 14;
    margin: 0 2 0 2;
    min-height: 1;
    height: 1;
    text-style: none;
}
#style_toolbar Select {
    width: 14;
    margin: 0 2 1 2;
}
#style_toolbar .label {
    text-align: center;
    text-style: bold;
    width: 100%;
    padding-bottom: 1;
}
#style_toolbar .hint {
    color: $text-muted;
    text-align: center;
    width: 100%;
    padding-top: 1;
}
"""


class WhiteboardScreen(Screen[None]):
    BLANK = True
    """Interactive whiteboard editor.

    Vim-style keys:

    * ``j / k / h / l``  \u2014 select the nearest box in that direction
      (45\u00b0 rotated-quadrant search; aspect-compensated distance).
      Terminal chars are ~2:1 (height:width), so vertical gaps count
      double when computing visual proximity.
    * ``J / K / H / L``  \u2014 move the selected box by a visually equal
      amount (10 chars horizontally or 5 chars vertically).
    * ``n``              \u2014 create a new box at the cursor.
    * ``r``              \u2014 rename the selected box (label prompt).
    * ``x``              \u2014 delete the selected box (and its connectors).
    * ``c``              \u2014 start a connector from the selected box; press
      ``c`` on another box to finalise it.
    * ``tab / shift+tab``\u2014 cycle selection through boxes.
    * ``q / escape``     \u2014 leave the screen.
    """

    DEFAULT_CSS = _STATUS_CSS
    BINDINGS = [
        Binding("escape", "close", "back"),
        Binding("q", "close", "back"),
        # Selection (45° rotated-quadrant + proximity).
        Binding("h", "select_left", "\u2190", show=False),
        Binding("l", "select_right", "\u2192", show=False),
        Binding("j", "select_down", "\u2193", show=False),
        Binding("k", "select_up", "\u2191", show=False),
        # Movement (visually equal steps: 10 chars horiz = 5 chars vert).
        Binding("H", "move(-10, 0)", "\u2190\u2190", show=False),
        Binding("L", "move(10, 0)", "\u2192\u2192", show=False),
        Binding("J", "move(0, 5)", "\u2193\u2193", show=False),
        Binding("K", "move(0, -5)", "\u2191\u2191", show=False),
        # Selection.
        Binding("tab", "cycle(1)", "next box"),
        Binding("shift+tab", "cycle(-1)", "prev box"),
        # Box operations.
        Binding("n", "new_box", "[n]ew box"),
        Binding("r", "rename_box", "[r]ename"),
        Binding("x", "delete_box", "[x] delete"),
        # Connector.
        Binding("c", "connect", "[c]onnect"),
        # Toolbar.
        Binding("b", "toggle_toolbar", "[b] style"),
    ]

    def __init__(self, whiteboard: Whiteboard) -> None:
        super().__init__()
        self._wb = whiteboard
        self._boxes: list[Box] = []
        self._connectors: list[Connector] = []
        self._selected_id: str | None = None
        # Set when the user presses ``c`` to start a connector; the next
        # ``c`` press on a different box finalises it.
        self._connect_source_id: str | None = None

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        # ScrollableContainer provides the scrollable viewport; the inner
        # Static renders the canvas at its intrinsic size (width: auto)
        # so lines never wrap. Overflow scrollbars appear automatically
        # when the board exceeds the visible area.
        with ScrollableContainer(id="canvas_scroll"):
            yield _Canvas(Text(" "), id="canvas", markup=False)
        # Floating style toolbar — hidden by default.
        with Vertical(id="style_toolbar"):
            yield Label("Style", classes="label")
            yield Label("Border", classes="label")
            yield Select(
                _BORDER_OPTIONS,
                prompt="",
                value="bold white",
                id="sel_border",
            )
            yield Label("Fill", classes="label")
            yield Select(
                _FILL_OPTIONS,
                prompt="",
                value="",
                id="sel_fill",
            )
            yield Button("Clear Fill", id="btn_clear", variant="error")
            yield Static(
                "[b] hide",
                classes="hint",
            )
        yield Static(" ", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._reload()

    # ------------------------------------------------------------------
    # data / rendering
    # ------------------------------------------------------------------

    def _reload(self) -> None:
        assert self._wb.id is not None
        self._boxes = wbs.list_boxes_std(self._wb.id)
        self._connectors = wbs.list_connectors_std(self._wb.id)
        if self._selected_id not in {b.id for b in self._boxes}:
            self._selected_id = self._boxes[0].id if self._boxes else None
        self._render()

    def _render(self) -> None:
        canvas = self.query_one("#canvas", Static)
        canvas.update(
            render_canvas(
                self._boxes,
                self._connectors,
                selected_box_id=self._selected_id,
            )
        )
        status = self.query_one("#status", Static)
        parts = [
            f"{self._wb.name}",
            f"{len(self._boxes)} boxes",
            f"{len(self._connectors)} connectors",
        ]
        if self._connect_source_id is not None:
            parts.append(f"connecting from #{self._connect_source_id}\u2026")
        elif self._selected_id is not None:
            parts.append(f"selected #{self._selected_id}")
        status.update(" \u2502 ".join(parts))
        self._maybe_refresh_toolbar()

    def _ensure_selected_visible(self) -> None:
        """Scroll the canvas viewport so the selected box is fully visible."""
        box = self._selected_box()
        if box is None:
            return
        container = self.query_one("#canvas_scroll", ScrollableContainer)
        viewport_w = container.size.width
        viewport_h = container.size.height
        if viewport_w <= 0 or viewport_h <= 0:
            return
        sx = container.scroll_x
        sy = container.scroll_y
        left = box.x
        top = box.y
        right = box.x + box.width - 1
        bottom = box.y + box.height - 1
        target_x = sx
        target_y = sy
        if left < sx:
            target_x = left
        elif right >= sx + viewport_w:
            target_x = right - viewport_w + 1
        if top < sy:
            target_y = top
        elif bottom >= sy + viewport_h:
            target_y = bottom - viewport_h + 1
        if target_x != sx or target_y != sy:
            container.scroll_to(target_x, target_y, animate=False)

    def _selected_box(self) -> Box | None:
        if self._selected_id is None:
            return None
        for b in self._boxes:
            if b.id == self._selected_id:
                return b

    def _handle_canvas_click(self, offset: Offset) -> None:
        """Select the box under the mouse cursor (if any)."""
        x, y = offset.x, offset.y
        for b in self._boxes:
            if b.id is None:
                continue
            if b.x <= x <= b.x + b.width - 1 and b.y <= y <= b.y + b.height - 1:
                self._selected_id = b.id
                self._render()
                self.call_after_refresh(self._ensure_selected_visible)
                return
        return None

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_cycle(self, step: int) -> None:
        if not self._boxes:
            return
        ids = [b.id for b in self._boxes if b.id is not None]
        if self._selected_id is None:
            self._selected_id = ids[0]
        else:
            i = (ids.index(self._selected_id) + step) % len(ids)
            self._selected_id = ids[i]
        self._render()
        self.call_after_refresh(self._ensure_selected_visible)

    # ------------------------------------------------------------------
    # Directional selection (45° rotated quadrants + Euclidean distance)
    # ------------------------------------------------------------------

    def _box_center(self, box: Box) -> tuple[float, float]:
        """Return the visual centre of *box* as (cx, cy)."""
        return (box.x + box.width / 2.0, box.y + box.height / 2.0)

    def _select_nearest_in_direction(
        self,
        *,
        s_sign: int,   # sign of (dx + dy)  -- rotated-u axis
        d_sign: int,   # sign of (dy - dx)  -- rotated-v axis
    ) -> None:
        """Select the nearest box whose centre lies in the target quadrant.

        Quadrants are defined after a 45° CCW rotation:

            s = dx + dy     (axis pointing down-right)
            d = dy - dx     (axis pointing down-left)

        The four hjkl directions map to:
            j (down)  : s > 0, d > 0
            k (up)    : s < 0, d < 0
            h (left)  : s < 0, d > 0
            l (right) : s > 0, d < 0
        """
        current = self._selected_box()
        if current is None:
            # Nothing selected yet — select the first box if any.
            if self._boxes:
                self._selected_id = self._boxes[0].id
                self._render()
                self.call_after_refresh(self._ensure_selected_visible)
            return

        cx, cy = self._box_center(current)

        best: tuple[str, float] | None = None  # (box_id, dist_sq)
        for b in self._boxes:
            if b.id == current.id or b.id is None:
                continue
            bx, by = self._box_center(b)
            dx = bx - cx
            dy = by - cy
            s = dx + dy
            d = dy - dx
            # Must be strictly inside the target quadrant (diagonal
            # boundaries are excluded so the four quadrants are disjoint).
            if (s > 0 if s_sign > 0 else s < 0) and (
                d > 0 if d_sign > 0 else d < 0
            ):
                # Aspect-compensated distance: chars are ~2:1 (h:w).
                # A 1-row vertical gap is visually ~2x a 1-col gap.
                dist_sq = dx * dx + (_ASPECT * dy) * (_ASPECT * dy)
                if best is None or dist_sq < best[1]:
                    best = (b.id, dist_sq)

        if best is not None:
            self._selected_id = best[0]
            self._render()
            self.call_after_refresh(self._ensure_selected_visible)

    def action_select_left(self) -> None:
        """Select the nearest box to the left (s<0, d>0)."""
        self._select_nearest_in_direction(s_sign=-1, d_sign=+1)

    def action_select_right(self) -> None:
        """Select the nearest box to the right (s>0, d<0)."""
        self._select_nearest_in_direction(s_sign=+1, d_sign=-1)

    def action_select_down(self) -> None:
        """Select the nearest box below (s>0, d>0)."""
        self._select_nearest_in_direction(s_sign=+1, d_sign=+1)

    def action_select_up(self) -> None:
        """Select the nearest box above (s<0, d<0)."""
        self._select_nearest_in_direction(s_sign=-1, d_sign=-1)

    def action_move(self, dx: int, dy: int) -> None:
        box = self._selected_box()
        if box is None or box.id is None:
            return
        # Canvas auto-expands, so only clip at the origin.
        new_x = max(0, box.x + dx)
        new_y = max(0, box.y + dy)
        if new_x == box.x and new_y == box.y:
            return
        wbs.update_box_std(box.id, BoxUpdate(x=new_x, y=new_y))
        self._reload()
        self.call_after_refresh(self._ensure_selected_visible)

    def action_new_box(self) -> None:
        assert self._wb.id is not None
        # Stagger placement so new boxes don't pile up on top of each other.
        offset = (len(self._boxes) % 8) * 3
        box = wbs.create_box_std(
            BoxCreate(
                whiteboard_id=self._wb.id,
                label=f"Box {len(self._boxes) + 1}",
                x=2 + offset,
                y=2 + offset,
                width=16,
                height=3,
            )
        )
        self._selected_id = box.id
        self._reload()
        self.call_after_refresh(self._ensure_selected_visible)

    def action_rename_box(self) -> None:
        box = self._selected_box()
        if box is None or box.id is None:
            return

        def _after(new_label: str | None) -> None:
            if new_label is not None:
                wbs.update_box_std(box.id, BoxUpdate(label=new_label))
                self._reload()

        self.app.push_screen(RenameBoxScreen(box.label or ""), _after)

    def action_delete_box(self) -> None:
        box = self._selected_box()
        if box is None or box.id is None:
            return
        wbs.delete_box_std(box.id)
        self._selected_id = None
        self._connect_source_id = None
        self._reload()
        self.call_after_refresh(self._ensure_selected_visible)

    # ------------------------------------------------------------------
    # Toolbar helpers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn_clear":
            return
        box = self._selected_box()
        if box is None or box.id is None:
            return
        wbs.update_box_std(box.id, BoxUpdate(fill_style=None))
        self._reload()

    def _sync_toolbar(self) -> None:
        """Reflect the selected box's style in the toolbar controls."""
        box = self._selected_box()
        toolbar = self.query_one("#style_toolbar")
        if box is None:
            toolbar.styles.display = "none"
            return
        toolbar.styles.display = "block"
        self.query_one("#sel_border", Select).value = box.border_style or "bold white"
        self.query_one("#sel_fill", Select).value = box.fill_style or ""

    def _maybe_refresh_toolbar(self) -> None:
        """If the toolbar is visible, update its dropdowns to the selected box."""
        toolbar = self.query_one("#style_toolbar")
        if toolbar.styles.display == "none":
            return
        box = self._selected_box()
        if box is None:
            toolbar.styles.display = "none"
            return
        self.query_one("#sel_border", Select).value = box.border_style or "bold white"
        self.query_one("#sel_fill", Select).value = box.fill_style or ""

    def on_select_changed(self, event: Select.Changed) -> None:
        """Apply a style change from the toolbar Select widgets."""
        box = self._selected_box()
        if box is None or box.id is None:
            return
        sel_id = event.select.id
        raw = None if event.value == Select.NULL else event.value
        assert isinstance(raw, str)
        value = raw or None
        update = BoxUpdate()
        if sel_id == "sel_border":
            update.border_style = value  # type: ignore[assignment]
        elif sel_id == "sel_fill":
            update.fill_style = value
        if update.model_dump(exclude_unset=True):
            wbs.update_box_std(box.id, update)
            self._reload()

    def action_toggle_toolbar(self) -> None:
        toolbar = self.query_one("#style_toolbar")
        is_visible = toolbar.styles.display != "none"
        toolbar.styles.display = "none" if is_visible else "block"
        if not is_visible:
            self._sync_toolbar()
            self.query_one("#sel_border", Select).focus()

    def action_connect(self) -> None:
        box = self._selected_box()
        if box is None or box.id is None:
            return
        if self._connect_source_id is None:
            self._connect_source_id = box.id
            self._render()
            return
        if self._connect_source_id == box.id:
            # Second press on the same box cancels the pending connection.
            self._connect_source_id = None
            self._render()
            return
        assert self._wb.id is not None
        try:
            wbs.create_connector_std(
                ConnectorCreate(
                    whiteboard_id=self._wb.id,
                    source_box_id=self._connect_source_id,
                    target_box_id=box.id,
                )
            )
        finally:
            self._connect_source_id = None
        self._reload()
