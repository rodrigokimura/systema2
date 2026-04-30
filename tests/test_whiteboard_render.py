"""Tests for the whiteboard ASCII canvas renderer."""

from __future__ import annotations

from systema2.models import Box, Connector
from systema2.tui.screens.whiteboard import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    render_canvas,
)


def _box(
    box_id: int,
    x: int,
    y: int,
    *,
    width: int = 10,
    height: int = 3,
    label: str = "",
) -> Box:
    return Box(
        id=box_id,
        whiteboard_id=1,
        label=label or f"b{box_id}",
        x=x,
        y=y,
        width=width,
        height=height,
    )


def _plain(text) -> list[str]:
    """Return the rendered plain-text grid as a list of lines."""
    return text.plain.rstrip("\n").splitlines()


def test_canvas_has_expected_dimensions() -> None:
    out = _plain(render_canvas([], []))
    assert len(out) == CANVAS_HEIGHT
    # Every row is padded to the canvas width.
    for row in out:
        assert len(row) == CANVAS_WIDTH


def test_empty_canvas_is_all_whitespace() -> None:
    out = _plain(render_canvas([], []))
    assert all(set(row) <= {" "} for row in out)


def test_single_box_is_drawn_with_corners_and_label() -> None:
    box = _box(1, 2, 2, width=10, height=3, label="hello")
    out = _plain(render_canvas([box], []))
    # Top edge of the box.
    top = out[2]
    assert top[2] == "\u250c"
    assert top[11] == "\u2510"
    # Bottom edge.
    bottom = out[4]
    assert bottom[2] == "\u2514"
    assert bottom[11] == "\u2518"
    # Label lives inside the box.
    middle = out[3]
    assert "hello" in middle


def test_connector_between_two_boxes_draws_horizontal_line() -> None:
    a = _box(1, 2, 5, width=8, height=3, label="a")
    b = _box(2, 40, 5, width=8, height=3, label="b")
    conn = Connector(
        id=1, whiteboard_id=1, source_box_id=1, target_box_id=2
    )
    out = _plain(render_canvas([a, b], [conn]))
    # The two boxes share the same centre row; the connector's horizontal
    # leg runs along that row between them.
    row = out[6]  # (5 + 7) // 2 == 6
    # There should be ``\u2500`` characters between the two boxes.
    dash_count = row[10:40].count("\u2500")
    assert dash_count > 5, f"expected many dashes, got: {row!r}"
    # And a right-facing arrowhead where the line meets box b's left edge.
    assert "\u25b6" in row


def test_connector_between_stacked_boxes_uses_vertical_leg() -> None:
    a = _box(1, 10, 1, width=10, height=3, label="a")
    b = _box(2, 10, 20, width=10, height=3, label="b")
    conn = Connector(
        id=1, whiteboard_id=1, source_box_id=1, target_box_id=2
    )
    out = _plain(render_canvas([a, b], [conn]))
    # Somewhere between the two boxes there should be a vertical pipe on
    # the shared centre column.
    center_col = 14  # (10 + 19) // 2
    column_slice = [out[y][center_col] for y in range(5, 20)]
    assert column_slice.count("\u2502") >= 5


def test_selected_box_has_distinct_style() -> None:
    box = _box(1, 5, 5)
    text = render_canvas([box], [], selected_box_id=1)
    # The Rich ``Text`` records per-span styles; the selected style is
    # applied to the box characters.
    styles = {str(span.style) for span in text.spans}
    assert any("yellow" in s for s in styles)

    text2 = render_canvas([box], [], selected_box_id=None)
    styles2 = {str(span.style) for span in text2.spans}
    # Non-selected boxes never use the yellow highlight.
    assert not any("yellow" in s for s in styles2)


def test_boxes_are_drawn_on_top_of_connectors() -> None:
    # Place a connector endpoint so its horizontal leg would pass through
    # the interior of box ``b`` if the z-order were wrong.
    a = _box(1, 0, 5, width=8, height=3, label="a")
    b = _box(2, 20, 5, width=12, height=3, label="BBB")
    conn = Connector(
        id=1, whiteboard_id=1, source_box_id=1, target_box_id=2
    )
    out = _plain(render_canvas([a, b], [conn]))
    # Interior row of box b should contain its label, not a dash from the
    # connector.
    middle = out[6]
    assert "BBB" in middle
    # The characters inside the box borders must not be dashes.
    interior = middle[21:31]
    assert "\u2500" not in interior
