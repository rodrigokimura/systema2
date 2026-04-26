"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from systema2 import database as database_module
from systema2.api import app as fastapi_app
from systema2.database import get_session


def _make_in_memory_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Fresh in-memory SQLite session for API tests (via dependency override)."""
    engine = _make_in_memory_engine()
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def _get_session_override() -> Generator[Session, None, None]:
        yield session

    fastapi_app.dependency_overrides[get_session] = _get_session_override
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def db_engine(monkeypatch: pytest.MonkeyPatch) -> Generator[object, None, None]:
    """Swap the module-level engine for an in-memory one.

    Used by CLI and TUI tests. The service layer resolves the engine lazily
    via ``systema2.database.engine``, so patching this one attribute is
    sufficient. We also stub ``init_db`` so the CLI/TUI don't re-create
    tables on the real engine.
    """
    engine = _make_in_memory_engine()
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "init_db", lambda: None)

    # Patch the name where each module imported it (`from ... import init_db`).
    import systema2.cli.tasks as cli_tasks
    import systema2.cli.tui as cli_tui
    import systema2.tui.app as tui_app

    for mod in (cli_tasks, cli_tui, tui_app):
        monkeypatch.setattr(mod, "init_db", lambda: None)

    yield engine
    engine.dispose()
