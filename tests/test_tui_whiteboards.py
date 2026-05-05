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


async def test_jkhl_moves_selected_box(db_engine) -> None:
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
        await pilot.press("l")  # right
        await pilot.press("l")
        await pilot.press("j")  # down
        await pilot.pause()

    with Session(db_engine) as s:
        fresh = s.get(Box, box.id)
    assert fresh is not None
    # Two rights, one down from (10, 10).
    assert (fresh.x, fresh.y) == (12, 11)


async def test_capital_L_moves_five_cells(db_engine) -> None:
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
        await pilot.press("L")  # +5 right
        await pilot.press("J")  # +5 down
        await pilot.pause()

    with Session(db_engine) as s:
        fresh = s.get(Box, box.id)
    assert fresh is not None
    assert (fresh.x, fresh.y) == (15, 15)


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
