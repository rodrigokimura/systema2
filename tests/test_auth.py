"""API-key authentication tests.

These tests build a fresh ``TestClient`` (rather than using the ``client``
fixture from ``conftest``) so we can exercise ``SYSTEMA2_API_KEY`` being
set / unset before the app reads it.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from systema2.api import app as fastapi_app
from systema2.database import get_session
from systema2.repository import (
    AuthenticationError,
    HttpTaskRepository,
)
from systema2.models import TaskCreate


@pytest.fixture
def authed_client(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    """TestClient against an app configured with SYSTEMA2_API_KEY=secret."""
    monkeypatch.setenv("SYSTEMA2_API_KEY", "secret")

    def _get_session_override() -> Generator[Session, None, None]:
        yield session

    fastapi_app.dependency_overrides[get_session] = _get_session_override
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Server-side enforcement
# ---------------------------------------------------------------------------


def test_root_is_unauthenticated(authed_client: TestClient) -> None:
    # Health endpoint must remain reachable without credentials so that
    # probes / load balancers don't need the shared secret.
    r = authed_client.get("/")
    assert r.status_code == 200


def test_missing_api_key_returns_401(authed_client: TestClient) -> None:
    r = authed_client.get("/tasks")
    assert r.status_code == 401
    assert r.json()["detail"] == "Missing API key"
    assert r.headers.get("WWW-Authenticate") == "X-API-Key"


def test_wrong_api_key_returns_403(authed_client: TestClient) -> None:
    r = authed_client.get("/tasks", headers={"X-API-Key": "nope"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Invalid API key"


def test_correct_api_key_allows_request(authed_client: TestClient) -> None:
    r = authed_client.get("/tasks", headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    assert r.json() == []


def test_bearer_token_also_accepted(authed_client: TestClient) -> None:
    r = authed_client.get(
        "/tasks", headers={"Authorization": "Bearer secret"}
    )
    assert r.status_code == 200


def test_projects_router_also_protected(authed_client: TestClient) -> None:
    r = authed_client.get("/projects")
    assert r.status_code == 401

    r = authed_client.post(
        "/projects",
        json={"name": "p"},
        headers={"X-API-Key": "secret"},
    )
    assert r.status_code == 201


def test_no_api_key_configured_disables_auth(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Explicitly unset to guard against inherited environment.
    monkeypatch.delenv("SYSTEMA2_API_KEY", raising=False)
    r = client.get("/tasks")
    assert r.status_code == 200


def test_blank_api_key_disables_auth(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYSTEMA2_API_KEY", "   ")
    r = client.get("/tasks")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Client-side (HttpTaskRepository) behaviour
# ---------------------------------------------------------------------------


def test_http_repo_sends_api_key_header(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYSTEMA2_API_KEY", "secret")

    def _get_session_override() -> Generator[Session, None, None]:
        yield session

    fastapi_app.dependency_overrides[get_session] = _get_session_override

    def _client_factory(self: HttpTaskRepository) -> httpx.Client:
        # Reproduce the production wiring but drive the in-process app.
        tc = TestClient(fastapi_app, base_url=self._base_url)
        tc.headers.update(self._headers())
        return tc

    monkeypatch.setattr(HttpTaskRepository, "_client", _client_factory)

    repo = HttpTaskRepository(base_url="http://testserver")
    # Reads and writes should both succeed because the repo picks up
    # SYSTEMA2_API_KEY from the env and forwards it.
    created = repo.create_task(TaskCreate(title="authed"))
    assert created.id is not None
    assert [t.title for t in repo.list_tasks()] == ["authed"]

    fastapi_app.dependency_overrides.clear()


def test_http_repo_raises_authentication_error_on_bad_key(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYSTEMA2_API_KEY", "server-secret")

    def _get_session_override() -> Generator[Session, None, None]:
        yield session

    fastapi_app.dependency_overrides[get_session] = _get_session_override

    def _client_factory(self: HttpTaskRepository) -> httpx.Client:
        tc = TestClient(fastapi_app, base_url=self._base_url)
        tc.headers.update(self._headers())
        return tc

    monkeypatch.setattr(HttpTaskRepository, "_client", _client_factory)

    # Explicitly hand the repo a wrong key so the server's 403 path fires.
    repo = HttpTaskRepository(
        base_url="http://testserver", api_key="client-wrong"
    )
    with pytest.raises(AuthenticationError) as exc:
        repo.list_tasks()
    assert "403" in str(exc.value)

    fastapi_app.dependency_overrides.clear()


def test_http_repo_raises_authentication_error_when_key_missing(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYSTEMA2_API_KEY", "server-secret")

    def _get_session_override() -> Generator[Session, None, None]:
        yield session

    fastapi_app.dependency_overrides[get_session] = _get_session_override

    def _client_factory(self: HttpTaskRepository) -> httpx.Client:
        tc = TestClient(fastapi_app, base_url=self._base_url)
        tc.headers.update(self._headers())
        return tc

    monkeypatch.setattr(HttpTaskRepository, "_client", _client_factory)

    # ``api_key=""`` forces the repo to send no credentials even though
    # the env is set, exercising the 401 branch.
    repo = HttpTaskRepository(base_url="http://testserver", api_key="")
    with pytest.raises(AuthenticationError) as exc:
        repo.list_tasks()
    assert "401" in str(exc.value)

    fastapi_app.dependency_overrides.clear()
