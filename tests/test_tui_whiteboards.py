"""End-to-end Textual tests for the whiteboard screens."""

from __future__ import annotations

from sqlmodel import Session, select

from systema2 import whiteboard_services as wbs
from systema2.models import (
    Box,
    BoxCreate,
    Connector,
    ConnectorCreate,
    Whiteboard,
    WhiteboardCreate,
)
from systema2.tui import Systema2App
from systema2.tui.screens.whiteboard import WhiteboardScreen
from systema2.tui.screens.whiteboard_list import WhiteboardListScreen


# ---------------------------------------------------------------------------
# Whiteboard list screen
# ---------------------------------------------------------------------------


async def test_w_opens_whiteboard_list(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        assert isinstance(app.screen, WhiteboardListScreen)


async def test_n_creates_whiteboard_and_opens_it(db_engine) -> None:
    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        await pilot.press("n")  # new board -> opens editor
        await pilot.pause()
        assert isinstance(app.screen, WhiteboardScreen)

    with Session(db_engine) as s:
        boards = list(s.exec(select(Whiteboard)).all())
    assert len(boards) == 1
    assert boards[0].name == "whiteboard 1"


async def test_list_screen_x_deletes_whiteboard(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="doomed"))
    assert wb.id is not None

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

    with Session(db_engine) as s:
        assert list(s.exec(select(Whiteboard)).all()) == []


# ---------------------------------------------------------------------------
# Whiteboard editor screen: boxes
# ---------------------------------------------------------------------------


async def test_n_creates_a_box_on_the_whiteboard(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        assert isinstance(app.screen, WhiteboardScreen)
        await pilot.press("n")  # new box
        await pilot.pause()

    with Session(db_engine) as s:
        boxes = list(s.exec(select(Box)).all())
    assert len(boxes) == 1
    assert boxes[0].whiteboard_id == wb.id


# ---------------------------------------------------------------------------
# Proximity selection (hjkl with 45° rotated quadrants)
# ---------------------------------------------------------------------------


async def test_h_selects_nearest_left_box(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    center = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="center", x=40, y=20)
    )
    left_near = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="left-near", x=10, y=21)
    )
    left_far = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="left-far", x=5, y=22)
    )
    # Place a box above so it is excluded by the quadrant filter.
    wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="above", x=39, y=5)
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = WhiteboardScreen(wb)
        app.push_screen(screen)
        await pilot.pause()
        # Force selection to the center box.
        screen._selected_id = center.id
        screen._render()
        await pilot.press("h")
        await pilot.pause()

    assert screen._selected_id == left_near.id


async def test_l_selects_nearest_right_box(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    center = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="center", x=10, y=20)
    )
    right_box = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="right", x=60, y=22)
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = WhiteboardScreen(wb)
        app.push_screen(screen)
        await pilot.pause()
        screen._selected_id = center.id
        screen._render()
        await pilot.press("l")
        await pilot.pause()

    assert screen._selected_id == right_box.id


async def test_j_selects_nearest_down_box(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    top_box = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="top", x=10, y=5)
    )
    below = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="below", x=12, y=30)
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = WhiteboardScreen(wb)
        app.push_screen(screen)
        await pilot.pause()
        screen._selected_id = top_box.id
        screen._render()
        await pilot.press("j")
        await pilot.pause()

    assert screen._selected_id == below.id


async def test_k_selects_nearest_up_box(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    bottom = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="bottom", x=10, y=30)
    )
    above = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="above", x=8, y=5)
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = WhiteboardScreen(wb)
        app.push_screen(screen)
        await pilot.pause()
        screen._selected_id = bottom.id
        screen._render()
        await pilot.press("k")
        await pilot.pause()

    assert screen._selected_id == above.id


async def test_h_with_no_left_box_does_nothing(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    only = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="only", x=50, y=20)
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = WhiteboardScreen(wb)
        app.push_screen(screen)
        await pilot.pause()
        screen._selected_id = only.id
        screen._render()
        await pilot.press("h")
        await pilot.pause()

    assert screen._selected_id == only.id


async def test_proximity_prefers_y_nearer_box_with_aspect(db_engine) -> None:
    """With a 2:1 terminal aspect ratio, a smaller vertical gap can
    outweigh a larger horizontal gap in visual distance.

    From a box at (0, 0) we create two left-side boxes:
    - left_far:  (-10,  1)  → small dy, so visually close
    - left_near: (-10, 10)  → same dx but large dy, visually farther

    The aspect-compensated distance for left_far is ~sqrt(10^2 + (2*1)^2)
    ≈ 10.2, while left_near is ~sqrt(10^2 + (2*10)^2) ≈ 22.4.
    Pressing ``h`` should therefore pick left_far.
    """
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    origin = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="origin", x=30, y=20)
    )
    left_far = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="lf", x=20, y=21)
    )
    left_near = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="ln", x=20, y=10)
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = WhiteboardScreen(wb)
        app.push_screen(screen)
        await pilot.pause()
        screen._selected_id = origin.id
        screen._render()
        await pilot.press("h")
        await pilot.pause()

    assert screen._selected_id == left_far.id


async def test_proximity_diagonal_equidistant_at_2to1_aspect(db_engine) -> None:
    """At 2:1 aspect, a box offset (20, 0) horizontally and a box offset
    (0, 10) vertically have the same *visual* distance from the origin.

    We place three boxes:
    - right:   (20, 0)  from origin → dx=20, dy=0  → dist=20
    - below:   (0, 10)  from origin → dx=0,  dy=10 → aspect-dist=20
    - diag:    (20, 10) from origin → dx=20, dy=10 → aspect-dist=~28

    Pressing ``l`` from origin should pick *right* (nearest in that
    quadrant; below is in the down quadrant and diag is farther).
    """
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    origin = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="origin", x=20, y=20)
    )
    right = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="right", x=40, y=20)
    )
    wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="below", x=20, y=30)
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = WhiteboardScreen(wb)
        app.push_screen(screen)
        await pilot.pause()
        screen._selected_id = origin.id
        screen._render()
        await pilot.press("l")
        await pilot.pause()

    assert screen._selected_id == right.id


async def test_shift_hjkl_can_move_past_old_fixed_limits(db_engine) -> None:
    """With fixed-size canvas movement was clamped at (120, 40).
    The auto-expanding canvas should allow boxes to move beyond that."""
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    box = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="a", x=110, y=35)
    )
    assert box.id is not None

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        # L (+10 right) should go past the old 120-char limit.
        # J (+5 down) should go past the old 40-char limit.
        await pilot.press("L")
        await pilot.press("J")
        await pilot.pause()

    with Session(db_engine) as s:
        fresh = s.get(Box, box.id)
    assert fresh is not None
    assert fresh.x == 120  # 110 + 10, no clamping at 120 - width
    assert fresh.y == 40   # 35 + 5, no clamping at 40 - height


async def test_shift_hjkl_still_moves_box(db_engine) -> None:
    """Uppercase HJKL (Shift+hjkl) moves the selected box by a visually
    equal amount: 10 chars horizontally or 5 chars vertically.
    """
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    box = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="a", x=10, y=10)
    )
    assert box.id is not None

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        await pilot.press("L")  # +10 right (Shift+l)
        await pilot.press("J")  # +5 down (Shift+j)
        await pilot.pause()

    with Session(db_engine) as s:
        fresh = s.get(Box, box.id)
    assert fresh is not None
    assert (fresh.x, fresh.y) == (20, 15)


async def test_x_deletes_selected_box(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="a", x=0, y=0)
    )

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

    with Session(db_engine) as s:
        boxes = list(s.exec(select(Box)).all())
    assert boxes == []


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------


async def test_c_c_between_two_boxes_creates_connector(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    a = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="a", x=0, y=0)
    )
    b = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="b", x=20, y=0)
    )
    assert a.id and b.id

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = WhiteboardScreen(wb)
        app.push_screen(screen)
        await pilot.pause()
        # Boxes are ordered by nanoid (lexicographic), not creation order.
        # Ensure ``a`` is selected before arming the connector.
        if screen._selected_id == b.id:
            await pilot.press("tab")  # move from b to a
            await pilot.pause()
        # Now ``a`` is selected — arm, cycle to ``b``, commit.
        await pilot.press("c")  # start from a
        await pilot.press("tab")  # select b
        await pilot.press("c")  # finish -> a → b
        await pilot.pause()

    with Session(db_engine) as s:
        conns = list(s.exec(select(Connector)).all())
    assert len(conns) == 1
    assert conns[0].source_box_id == a.id
    assert conns[0].target_box_id == b.id


async def test_c_c_same_box_cancels_pending(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    wbs.create_box_std(BoxCreate(whiteboard_id=wb.id, label="a"))

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        await pilot.press("c")
        await pilot.press("c")  # same box -> cancels
        await pilot.pause()

    with Session(db_engine) as s:
        conns = list(s.exec(select(Connector)).all())
    assert conns == []


async def test_r_opens_rename_modal_and_saves(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    box = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="old", x=0, y=0)
    )
    assert box.id is not None

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        # Modal should be on top.
        from systema2.tui.screens.rename_box import RenameBoxScreen
        from textual.widgets import Input

        assert isinstance(app.screen, RenameBoxScreen)
        # Replace the pre-filled text.
        app.screen.query_one("#label", Input).value = "renamed"
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    with Session(db_engine) as s:
        fresh = s.get(Box, box.id)
    assert fresh is not None
    assert fresh.label == "renamed"


async def test_r_rename_modal_cancel_preserves_label(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))
    assert wb.id is not None
    box = wbs.create_box_std(
        BoxCreate(whiteboard_id=wb.id, label="keep", x=0, y=0)
    )
    assert box.id is not None

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    with Session(db_engine) as s:
        fresh = s.get(Box, box.id)
    assert fresh is not None
    assert fresh.label == "keep"


async def test_escape_closes_editor(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="w"))

    app = Systema2App()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        assert isinstance(app.screen, WhiteboardScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, WhiteboardScreen)
