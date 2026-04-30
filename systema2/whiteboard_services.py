"""Whiteboard / Box / Connector service layer.

Kept separate from :mod:`systema2.services` (tasks, projects) to avoid
that module growing unbounded. Used by the CLI and TUI; there is no
HTTP API for whiteboards yet.

Domain errors raised here are translated by the TUI/CLI into user-
visible messages.
"""

from __future__ import annotations

from sqlmodel import Session, select

from systema2 import database
from systema2.models import (
    Box,
    BoxCreate,
    BoxUpdate,
    Connector,
    ConnectorCreate,
    ConnectorUpdate,
    Whiteboard,
    WhiteboardCreate,
    WhiteboardUpdate,
    _utcnow,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WhiteboardNotFoundError(LookupError):
    def __init__(self, whiteboard_id: int) -> None:
        super().__init__(f"Whiteboard {whiteboard_id} not found")
        self.whiteboard_id = whiteboard_id


class BoxNotFoundError(LookupError):
    def __init__(self, box_id: int) -> None:
        super().__init__(f"Box {box_id} not found")
        self.box_id = box_id


class ConnectorValidationError(ValueError):
    """Raised when a connector would be invalid (self-loop, cross-board)."""


def _session() -> Session:
    return Session(database.engine)


# ---------------------------------------------------------------------------
# Whiteboards
# ---------------------------------------------------------------------------


def list_whiteboards(session: Session) -> list[Whiteboard]:
    return list(session.exec(select(Whiteboard).order_by(Whiteboard.id)).all())


def get_whiteboard(session: Session, whiteboard_id: int) -> Whiteboard | None:
    return session.get(Whiteboard, whiteboard_id)


def create_whiteboard(
    session: Session, payload: WhiteboardCreate
) -> Whiteboard:
    wb = Whiteboard.model_validate(payload)
    session.add(wb)
    session.commit()
    session.refresh(wb)
    return wb


def update_whiteboard(
    session: Session, whiteboard_id: int, payload: WhiteboardUpdate
) -> Whiteboard | None:
    wb = session.get(Whiteboard, whiteboard_id)
    if wb is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(wb, k, v)
    wb.updated_at = _utcnow()
    session.add(wb)
    session.commit()
    session.refresh(wb)
    return wb


def delete_whiteboard(session: Session, whiteboard_id: int) -> bool:
    wb = session.get(Whiteboard, whiteboard_id)
    if wb is None:
        return False
    # Cascade-delete connectors first (they depend on boxes), then boxes.
    for c in session.exec(
        select(Connector).where(Connector.whiteboard_id == whiteboard_id)
    ).all():
        session.delete(c)
    for b in session.exec(
        select(Box).where(Box.whiteboard_id == whiteboard_id)
    ).all():
        session.delete(b)
    session.delete(wb)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Boxes
# ---------------------------------------------------------------------------


def list_boxes(session: Session, whiteboard_id: int) -> list[Box]:
    return list(
        session.exec(
            select(Box)
            .where(Box.whiteboard_id == whiteboard_id)
            .order_by(Box.id)
        ).all()
    )


def get_box(session: Session, box_id: int) -> Box | None:
    return session.get(Box, box_id)


def create_box(session: Session, payload: BoxCreate) -> Box:
    if session.get(Whiteboard, payload.whiteboard_id) is None:
        raise WhiteboardNotFoundError(payload.whiteboard_id)
    box = Box.model_validate(payload)
    session.add(box)
    session.commit()
    session.refresh(box)
    return box


def update_box(
    session: Session, box_id: int, payload: BoxUpdate
) -> Box | None:
    box = session.get(Box, box_id)
    if box is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(box, k, v)
    box.updated_at = _utcnow()
    session.add(box)
    session.commit()
    session.refresh(box)
    return box


def delete_box(session: Session, box_id: int) -> bool:
    box = session.get(Box, box_id)
    if box is None:
        return False
    # Drop any connectors that reference this box.
    for c in session.exec(
        select(Connector).where(
            (Connector.source_box_id == box_id)
            | (Connector.target_box_id == box_id)
        )
    ).all():
        session.delete(c)
    session.delete(box)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------


def list_connectors(session: Session, whiteboard_id: int) -> list[Connector]:
    return list(
        session.exec(
            select(Connector)
            .where(Connector.whiteboard_id == whiteboard_id)
            .order_by(Connector.id)
        ).all()
    )


def get_connector(session: Session, connector_id: int) -> Connector | None:
    return session.get(Connector, connector_id)


def create_connector(
    session: Session, payload: ConnectorCreate
) -> Connector:
    if payload.source_box_id == payload.target_box_id:
        raise ConnectorValidationError(
            "A connector cannot loop from a box back to itself."
        )
    source = session.get(Box, payload.source_box_id)
    if source is None:
        raise BoxNotFoundError(payload.source_box_id)
    target = session.get(Box, payload.target_box_id)
    if target is None:
        raise BoxNotFoundError(payload.target_box_id)
    if (
        source.whiteboard_id != payload.whiteboard_id
        or target.whiteboard_id != payload.whiteboard_id
    ):
        raise ConnectorValidationError(
            "Source and target boxes must belong to the connector's whiteboard."
        )
    conn = Connector.model_validate(payload)
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn


def update_connector(
    session: Session, connector_id: int, payload: ConnectorUpdate
) -> Connector | None:
    conn = session.get(Connector, connector_id)
    if conn is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(conn, k, v)
    conn.updated_at = _utcnow()
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn


def delete_connector(session: Session, connector_id: int) -> bool:
    conn = session.get(Connector, connector_id)
    if conn is None:
        return False
    session.delete(conn)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Session-less convenience wrappers (used by CLI/TUI)
# ---------------------------------------------------------------------------


def list_whiteboards_std() -> list[Whiteboard]:
    with _session() as s:
        return list_whiteboards(s)


def get_whiteboard_std(whiteboard_id: int) -> Whiteboard | None:
    with _session() as s:
        return get_whiteboard(s, whiteboard_id)


def create_whiteboard_std(payload: WhiteboardCreate) -> Whiteboard:
    with _session() as s:
        return create_whiteboard(s, payload)


def update_whiteboard_std(
    whiteboard_id: int, payload: WhiteboardUpdate
) -> Whiteboard | None:
    with _session() as s:
        return update_whiteboard(s, whiteboard_id, payload)


def delete_whiteboard_std(whiteboard_id: int) -> bool:
    with _session() as s:
        return delete_whiteboard(s, whiteboard_id)


def list_boxes_std(whiteboard_id: int) -> list[Box]:
    with _session() as s:
        return list_boxes(s, whiteboard_id)


def create_box_std(payload: BoxCreate) -> Box:
    with _session() as s:
        return create_box(s, payload)


def update_box_std(box_id: int, payload: BoxUpdate) -> Box | None:
    with _session() as s:
        return update_box(s, box_id, payload)


def delete_box_std(box_id: int) -> bool:
    with _session() as s:
        return delete_box(s, box_id)


def list_connectors_std(whiteboard_id: int) -> list[Connector]:
    with _session() as s:
        return list_connectors(s, whiteboard_id)


def create_connector_std(payload: ConnectorCreate) -> Connector:
    with _session() as s:
        return create_connector(s, payload)


def delete_connector_std(connector_id: int) -> bool:
    with _session() as s:
        return delete_connector(s, connector_id)
