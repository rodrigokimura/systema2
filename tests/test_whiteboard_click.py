"""Tests for mouse click selection on the whiteboard canvas."""

from __future__ import annotations

from systema2 import whiteboard_services as wbs
from systema2.models import BoxCreate, WhiteboardCreate
from systema2.tui import Systema2App
from systema2.tui.screens.whiteboard import WhiteboardScreen, _Canvas
from textual.events import MouseDown, MouseMove, MouseUp


async def test_drag_on_blank_space_pans(db_engine) -> None:
    """Dragging on blank space must pan the canvas, not treat it as a click."""
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="pan"))
    wbs.create_box_std(BoxCreate(whiteboard_id=wb.id, x=150, y=5, width=10, height=3, label="far"))

    app = Systema2App()
    async with app.run_test(size=(40, 20)) as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, WhiteboardScreen)
        sc = screen.query_one("#canvas_scroll")
        canvas = screen.query_one("#canvas", _Canvas)

        # Drag left 10 from blank space (x=15 → x=5).
        screen._forward_event(
            MouseDown(
                widget=canvas, x=15, y=5,
                delta_x=0, delta_y=0, button=1,
                shift=False, meta=False, ctrl=False,
                screen_x=15, screen_y=5,
            )
        )
        await pilot.pause()
        screen._forward_event(
            MouseMove(
                widget=canvas, x=5, y=5,
                delta_x=-10, delta_y=0, button=1,
                shift=False, meta=False, ctrl=False,
                screen_x=5, screen_y=5,
            )
        )
        await pilot.pause()
        # Panning left reveals content to the right.
        assert sc.scroll_x == 10

        screen._forward_event(
            MouseUp(
                widget=canvas, x=5, y=5,
                delta_x=0, delta_y=0, button=1,
                shift=False, meta=False, ctrl=False,
                screen_x=5, screen_y=5,
            )
        )
        await pilot.pause()
        assert app.mouse_captured is None


async def test_click_on_box_selects_it(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="click"))
    box_a = wbs.create_box_std(BoxCreate(whiteboard_id=wb.id, x=3, y=3, width=10, height=3, label="a"))
    box_b = wbs.create_box_std(BoxCreate(whiteboard_id=wb.id, x=30, y=10, width=10, height=3, label="b"))

    app = Systema2App()
    async with app.run_test(size=(40, 20)) as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, WhiteboardScreen)
        canvas = screen.query_one("#canvas", _Canvas)

        # Initially the first box (by DB order) is selected
        # — but order is by nanoid, so just assert clicking works.
        screen._selected_id = box_a.id

        # Click inside box_b.
        screen._forward_event(
            MouseDown(
                widget=canvas,
                x=32,
                y=11,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=32,
                screen_y=11,
            )
        )
        await pilot.pause()
        screen._forward_event(
            MouseUp(
                widget=canvas,
                x=32,
                y=11,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=32,
                screen_y=11,
            )
        )
        await pilot.pause()
        assert screen._selected_id == box_b.id


async def test_click_outside_boxes_selects_nothing(db_engine) -> None:
    wb = wbs.create_whiteboard_std(WhiteboardCreate(name="click"))
    box_a = wbs.create_box_std(BoxCreate(whiteboard_id=wb.id, x=3, y=3, width=10, height=3, label="a"))

    app = Systema2App()
    async with app.run_test(size=(40, 20)) as pilot:
        await pilot.pause()
        app.push_screen(WhiteboardScreen(wb))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, WhiteboardScreen)
        canvas = screen.query_one("#canvas", _Canvas)

        screen._selected_id = box_a.id

        # Click on empty space away from the box.
        screen._forward_event(
            MouseDown(
                widget=canvas,
                x=25,
                y=25,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=25,
                screen_y=25,
            )
        )
        await pilot.pause()
        screen._forward_event(
            MouseUp(
                widget=canvas,
                x=25,
                y=25,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=25,
                screen_y=25,
            )
        )
        await pilot.pause()
        # Selection unchanged.
        assert screen._selected_id == box_a.id
