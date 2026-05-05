"""Service-layer tests for whiteboards, boxes, and connectors."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from systema2 import whiteboard_services as wbs
from systema2.models import (
    BoxCreate,
    BoxUpdate,
    ConnectorCreate,
    ConnectorUpdate,
    WhiteboardCreate,
    WhiteboardUpdate,
)


# ---------------------------------------------------------------------------
# Whiteboards
# ---------------------------------------------------------------------------


def test_create_and_list_whiteboards(session: Session) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="planning"))
    assert wb.id is not None
    assert wb.name == "planning"

    wbs.create_whiteboard(session, WhiteboardCreate(name="architecture"))
    names = sorted(w.name for w in wbs.list_whiteboards(session))
    assert names == ["architecture", "planning"]


def test_update_whiteboard(session: Session) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="old"))
    assert wb.id is not None
    updated = wbs.update_whiteboard(
        session, wb.id, WhiteboardUpdate(name="new", description="d")
    )
    assert updated is not None
    assert updated.name == "new"
    assert updated.description == "d"


def test_delete_whiteboard_cascades_boxes_and_connectors(
    session: Session,
) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="doomed"))
    assert wb.id is not None
    a = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="a"))
    b = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="b"))
    assert a.id is not None and b.id is not None
    wbs.create_connector(
        session,
        ConnectorCreate(
            whiteboard_id=wb.id, source_box_id=a.id, target_box_id=b.id
        ),
    )

    assert wbs.delete_whiteboard(session, wb.id) is True
    assert wbs.list_whiteboards(session) == []
    assert wbs.list_boxes(session, wb.id) == []
    assert wbs.list_connectors(session, wb.id) == []


# ---------------------------------------------------------------------------
# Boxes
# ---------------------------------------------------------------------------


def test_create_box_requires_existing_whiteboard(session: Session) -> None:
    with pytest.raises(wbs.WhiteboardNotFoundError) as exc:
        wbs.create_box(
            session, BoxCreate(whiteboard_id="nonexistent", label="x")
        )
    assert exc.value.whiteboard_id == "nonexistent"


def test_update_and_move_box(session: Session) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="b"))
    assert wb.id is not None
    box = wbs.create_box(
        session,
        BoxCreate(whiteboard_id=wb.id, label="hi", x=1, y=1),
    )
    assert box.id is not None
    moved = wbs.update_box(session, box.id, BoxUpdate(x=10, y=5))
    assert moved is not None
    assert (moved.x, moved.y) == (10, 5)


def test_delete_box_drops_its_connectors(session: Session) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="w"))
    assert wb.id is not None
    a = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="a"))
    b = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="b"))
    c = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="c"))
    assert a.id and b.id and c.id
    wbs.create_connector(
        session,
        ConnectorCreate(
            whiteboard_id=wb.id, source_box_id=a.id, target_box_id=b.id
        ),
    )
    wbs.create_connector(
        session,
        ConnectorCreate(
            whiteboard_id=wb.id, source_box_id=b.id, target_box_id=c.id
        ),
    )

    assert wbs.delete_box(session, b.id) is True
    remaining = wbs.list_connectors(session, wb.id)
    # Only connectors touching ``b`` were affected; none survive because
    # both referenced it.
    assert remaining == []


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------


def test_connector_happy_path(session: Session) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="w"))
    assert wb.id is not None
    a = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="a"))
    b = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="b"))
    assert a.id and b.id
    conn = wbs.create_connector(
        session,
        ConnectorCreate(
            whiteboard_id=wb.id,
            source_box_id=a.id,
            target_box_id=b.id,
            label="flows to",
        ),
    )
    assert conn.id is not None
    assert [c.id for c in wbs.list_connectors(session, wb.id)] == [conn.id]


def test_connector_self_loop_rejected(session: Session) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="w"))
    assert wb.id is not None
    a = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="a"))
    assert a.id is not None
    with pytest.raises(wbs.ConnectorValidationError):
        wbs.create_connector(
            session,
            ConnectorCreate(
                whiteboard_id=wb.id, source_box_id=a.id, target_box_id=a.id
            ),
        )


def test_connector_cross_whiteboard_rejected(session: Session) -> None:
    wb1 = wbs.create_whiteboard(session, WhiteboardCreate(name="1"))
    wb2 = wbs.create_whiteboard(session, WhiteboardCreate(name="2"))
    assert wb1.id is not None and wb2.id is not None
    a = wbs.create_box(session, BoxCreate(whiteboard_id=wb1.id, label="a"))
    b = wbs.create_box(session, BoxCreate(whiteboard_id=wb2.id, label="b"))
    assert a.id and b.id
    with pytest.raises(wbs.ConnectorValidationError):
        wbs.create_connector(
            session,
            ConnectorCreate(
                whiteboard_id=wb1.id, source_box_id=a.id, target_box_id=b.id
            ),
        )


def test_connector_unknown_source_or_target(session: Session) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="w"))
    assert wb.id is not None
    a = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="a"))
    assert a.id is not None
    with pytest.raises(wbs.BoxNotFoundError):
        wbs.create_connector(
            session,
            ConnectorCreate(
                whiteboard_id=wb.id,
                source_box_id=a.id,
                target_box_id="nonexistent",
            ),
        )
    with pytest.raises(wbs.BoxNotFoundError):
        wbs.create_connector(
            session,
            ConnectorCreate(
                whiteboard_id=wb.id,
                source_box_id="nonexistent",
                target_box_id=a.id,
            ),
        )


def test_update_and_delete_connector(session: Session) -> None:
    wb = wbs.create_whiteboard(session, WhiteboardCreate(name="w"))
    assert wb.id is not None
    a = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="a"))
    b = wbs.create_box(session, BoxCreate(whiteboard_id=wb.id, label="b"))
    assert a.id and b.id
    conn = wbs.create_connector(
        session,
        ConnectorCreate(
            whiteboard_id=wb.id, source_box_id=a.id, target_box_id=b.id
        ),
    )
    assert conn.id is not None

    updated = wbs.update_connector(
        session, conn.id, ConnectorUpdate(label="tagged")
    )
    assert updated is not None
    assert updated.label == "tagged"

    assert wbs.delete_connector(session, conn.id) is True
    assert wbs.list_connectors(session, wb.id) == []
