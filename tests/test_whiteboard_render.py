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


def test_horizontal_s_shape_has_two_corner_bends() -> None:
    # A is upper-left; B is lower-right. The connector should be a
    # horizontal S: leave A horizontally, drop down at the midpoint,
    # and arrive at B horizontally. Two bends are expected: ┐ on
    # A's centre row and └ on B's centre row, both on the same midpoint
    # column with a vertical run of │ between them.
    a = _box(1, 2, 2, width=10, height=3, label="a")
    b = _box(2, 40, 20, width=10, height=3, label="b")
    conn = Connector(
        id=1, whiteboard_id=1, source_box_id=1, target_box_id=2
    )
    out = _plain(render_canvas([a, b], [conn]))
    # A's centre row is y=3, B's centre row is y=21. Ignore the row
    # containing A's top-right ┐ corner (y=2).
    sy, ty = 3, 21
    row_src = out[sy]
    row_dst = out[ty]
    # The horizontal legs leave A to the right and enter B from the
    # left, so the ┐ bend is the *last* ┐ on sy (after A's ┐ corner)
    # and the └ bend is on ty (B has no └ on its centre row).
    assert "\u2510" in row_src, "expected a ┐ bend on A's centre row"
    assert "\u2514" in row_dst, "expected a └ bend on B's centre row"
    col_topbend = row_src.rindex("\u2510")
    col_botbend = row_dst.index("\u2514")
    assert col_topbend == col_botbend, (
        f"┐ at col {col_topbend} but └ at col {col_botbend}"
    )
    # Vertical run of │ on the midpoint column strictly between the
    # two rows.
    pipes = sum(1 for y in range(sy + 1, ty) if out[y][col_topbend] == "\u2502")
    assert pipes >= 3, f"expected ≥ 3 vertical pipes, got {pipes}"
    # Arrowhead on B's centre row.
    assert "\u25b6" in row_dst


def test_vertical_s_shape_has_two_corner_bends() -> None:
    # Vertically-dominant separation: the vertical gap is larger than
    # the horizontal one, so the router picks a vertical S. Expect:
    # exit A downward, turn right at the midpoint row, descend into B.
    a = _box(1, 20, 1, width=8, height=3, label="a")
    b = _box(2, 40, 30, width=8, height=3, label="b")
    conn = Connector(
        id=1, whiteboard_id=1, source_box_id=1, target_box_id=2
    )
    out = _plain(render_canvas([a, b], [conn]))
    # The two bends for a down-right vertical S are └ on A's column
    # and ┐ on B's column, both sitting on the midpoint row.
    src_col = 23  # A centre column: (20 + 27) // 2
    dst_col = 43  # B centre column: (40 + 47) // 2
    # Find the midpoint row by scanning A's column for a bend.
    my = None
    for y, row in enumerate(out):
        if row[src_col] == "\u2514":
            my = y
            break
    assert my is not None, "expected └ bend on A's centre column"
    assert out[my][dst_col] == "\u2510", (
        f"expected ┐ bend on B's centre column at row {my}, "
        f"got {out[my][dst_col]!r}"
    )
    # Horizontal run between the two bends.
    dashes = sum(
        1 for x in range(src_col + 1, dst_col) if out[my][x] == "\u2500"
    )
    assert dashes >= 3, f"expected ≥ 3 horizontal dashes, got {dashes}"
    # Arrowhead just above B (target_top - 1, dst_col).
    assert out[29][dst_col] == "\u25bc", (
        f"expected ▼ above B, got {out[29][dst_col]!r}"
    )


def test_s_shape_midpoint_column_is_between_the_two_boxes() -> None:
    # For a right-going horizontal S, the dogleg midpoint column must
    # sit in the clear space between the two boxes, not inside either.
    a = _box(1, 0, 0, width=10, height=3, label="a")  # cols 0..9
    b = _box(2, 50, 20, width=10, height=3, label="b")  # cols 50..59
    conn = Connector(
        id=1, whiteboard_id=1, source_box_id=1, target_box_id=2
    )
    out = _plain(render_canvas([a, b], [conn]))
    # A's centre row is y=1; look for the connector's ┐ bend on that
    # row (the first ┐ is A's top-right corner on y=0, which we skip).
    row = out[1]
    assert "\u2510" in row, "expected a ┐ bend on A's centre row"
    col = row.rindex("\u2510")
    assert 10 <= col <= 49, f"midpoint ┐ at col {col}; expected in 10..49"


def test_s_shape_reverses_direction_for_left_going_connector() -> None:
    # Flip source and target: connector goes right-to-left, so the
    # arrowhead must be ◀ at the right edge of the target box.
    a = _box(1, 50, 2, width=10, height=3, label="a")
    b = _box(2, 2, 20, width=10, height=3, label="b")
    conn = Connector(
        id=1, whiteboard_id=1, source_box_id=1, target_box_id=2
    )
    out = _plain(render_canvas([a, b], [conn]))
    assert any("\u25c0" in row for row in out)
    # And no right-facing arrow should appear for this connector.
    assert not any("\u25b6" in row for row in out)


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
