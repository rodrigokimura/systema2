"""Task storage backends.

A ``TaskRepository`` is an abstract facade that CLI and TUI code uses to
talk to tasks without caring whether they live in a local SQLite DB or
behind an HTTP API.

Use :func:`get_repository` to obtain the backend selected by the current
mode (see :mod:`systema2.config`).
"""

from __future__ import annotations

from typing import Protocol

import httpx

from systema2 import services
from systema2.config import Mode, get_api_url, get_mode
from systema2.models import Task, TaskCreate, TaskUpdate


class RepositoryError(RuntimeError):
    """Raised when a repository call fails (e.g. network/HTTP error)."""


class TaskRepository(Protocol):
    def list_tasks(self) -> list[Task]: ...
    def get_task(self, task_id: int) -> Task | None: ...
    def create_task(self, payload: TaskCreate) -> Task: ...
    def update_task(self, task_id: int, payload: TaskUpdate) -> Task | None: ...
    def delete_task(self, task_id: int) -> bool: ...


# ---------------------------------------------------------------------------
# Local (direct DB) backend
# ---------------------------------------------------------------------------


class LocalTaskRepository:
    """Direct-DB repository backed by the service layer."""

    def list_tasks(self) -> list[Task]:
        return services.list_tasks_std()

    def get_task(self, task_id: int) -> Task | None:
        return services.get_task_std(task_id)

    def create_task(self, payload: TaskCreate) -> Task:
        return services.create_task_std(payload)

    def update_task(self, task_id: int, payload: TaskUpdate) -> Task | None:
        return services.update_task_std(task_id, payload)

    def delete_task(self, task_id: int) -> bool:
        return services.delete_task_std(task_id)


# ---------------------------------------------------------------------------
# Remote (HTTP API) backend
# ---------------------------------------------------------------------------


class HttpTaskRepository:
    """Repository that proxies to a running ``systema2`` FastAPI server."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        self._base_url = (base_url or get_api_url()).rstrip("/")
        self._timeout = timeout

    # --- helpers -----------------------------------------------------------

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base_url, timeout=self._timeout)

    @staticmethod
    def _to_task(data: dict) -> Task:
        # The API returns TaskRead; Task can be constructed from the same
        # fields (it's a superset).
        return Task.model_validate(data)

    def _handle_network_error(self, exc: httpx.HTTPError) -> RepositoryError:
        return RepositoryError(
            f"Could not reach systema2 server at {self._base_url}: {exc}"
        )

    # --- protocol ---------------------------------------------------------

    def list_tasks(self) -> list[Task]:
        try:
            with self._client() as c:
                r = c.get("/tasks")
                r.raise_for_status()
                return [self._to_task(item) for item in r.json()]
        except httpx.HTTPError as exc:
            raise self._handle_network_error(exc) from exc

    def get_task(self, task_id: int) -> Task | None:
        try:
            with self._client() as c:
                r = c.get(f"/tasks/{task_id}")
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return self._to_task(r.json())
        except httpx.HTTPError as exc:
            raise self._handle_network_error(exc) from exc

    def create_task(self, payload: TaskCreate) -> Task:
        try:
            with self._client() as c:
                r = c.post("/tasks", json=payload.model_dump(mode="json"))
                r.raise_for_status()
                return self._to_task(r.json())
        except httpx.HTTPError as exc:
            raise self._handle_network_error(exc) from exc

    def update_task(self, task_id: int, payload: TaskUpdate) -> Task | None:
        body = payload.model_dump(mode="json", exclude_unset=True)
        try:
            with self._client() as c:
                r = c.patch(f"/tasks/{task_id}", json=body)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return self._to_task(r.json())
        except httpx.HTTPError as exc:
            raise self._handle_network_error(exc) from exc

    def delete_task(self, task_id: int) -> bool:
        try:
            with self._client() as c:
                r = c.delete(f"/tasks/{task_id}")
                if r.status_code == 404:
                    return False
                r.raise_for_status()
                return True
        except httpx.HTTPError as exc:
            raise self._handle_network_error(exc) from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_repository() -> TaskRepository:
    """Return the repository appropriate for the current mode.

    - ``local`` and ``server`` both use the local DB (the server *is* the
      owner of that DB).
    - ``client`` uses HTTP.
    """
    mode = get_mode()
    if mode is Mode.CLIENT:
        return HttpTaskRepository()
    return LocalTaskRepository()
