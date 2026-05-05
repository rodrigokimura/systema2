"""Task & Project storage backends.

A ``TaskRepository`` is a facade over both tasks and projects. CLI and
TUI code talks to it without caring whether operations hit the local
SQLite DB or a remote HTTP API.

Use :func:`get_repository` to obtain the backend selected by the current
mode (see :mod:`systema2.config`).
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

import httpx

from systema2 import services
from systema2.api.auth import API_KEY_HEADER
from systema2.config import Mode, get_api_key, get_api_url, get_mode
from systema2.models import (
    Priority,
    Project,
    ProjectCreate,
    ProjectUpdate,
    Task,
    TaskCreate,
    TaskUpdate,
)


class RepositoryError(RuntimeError):
    """Raised when a repository call fails (e.g. network/HTTP error)."""


class AuthenticationError(RepositoryError):
    """Raised when the server rejects our API key (401/403)."""


class ProjectNotFoundError(RepositoryError):
    """Raised when a CRUD call references a non-existent project."""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"Project {project_id} not found")
        self.project_id = project_id


class TaskRepository(Protocol):
    # Tasks --------------------------------------------------------------
    def list_tasks(
        self,
        *,
        project_id: str | None = None,
        unassigned: bool = False,
        priority: Priority | None = None,
        due_before: date | None = None,
    ) -> list[Task]: ...
    def get_task(self, task_id: str) -> Task | None: ...
    def create_task(self, payload: TaskCreate) -> Task: ...
    def update_task(self, task_id: str, payload: TaskUpdate) -> Task | None: ...
    def delete_task(self, task_id: str) -> bool: ...

    # Projects -----------------------------------------------------------
    def list_projects(self) -> list[Project]: ...
    def get_project(self, project_id: str) -> Project | None: ...
    def create_project(self, payload: ProjectCreate) -> Project: ...
    def update_project(
        self, project_id: str, payload: ProjectUpdate
    ) -> Project | None: ...
    def delete_project(self, project_id: str) -> bool: ...


# ---------------------------------------------------------------------------
# Local (direct DB) backend
# ---------------------------------------------------------------------------


class LocalTaskRepository:
    """Direct-DB repository backed by the service layer."""

    # Tasks --------------------------------------------------------------

    def list_tasks(
        self,
        *,
        project_id: str | None = None,
        unassigned: bool = False,
        priority: Priority | None = None,
        due_before: date | None = None,
    ) -> list[Task]:
        return services.list_tasks_std(
            project_id=project_id,
            unassigned=unassigned,
            priority=priority,
            due_before=due_before,
        )

    def get_task(self, task_id: str) -> Task | None:
        return services.get_task_std(task_id)

    def create_task(self, payload: TaskCreate) -> Task:
        try:
            return services.create_task_std(payload)
        except services.ProjectNotFoundError as exc:
            raise ProjectNotFoundError(exc.project_id) from exc

    def update_task(self, task_id: str, payload: TaskUpdate) -> Task | None:
        try:
            return services.update_task_std(task_id, payload)
        except services.ProjectNotFoundError as exc:
            raise ProjectNotFoundError(exc.project_id) from exc

    def delete_task(self, task_id: str) -> bool:
        return services.delete_task_std(task_id)

    # Projects -----------------------------------------------------------

    def list_projects(self) -> list[Project]:
        return services.list_projects_std()

    def get_project(self, project_id: str) -> Project | None:
        return services.get_project_std(project_id)

    def create_project(self, payload: ProjectCreate) -> Project:
        return services.create_project_std(payload)

    def update_project(
        self, project_id: str, payload: ProjectUpdate
    ) -> Project | None:
        return services.update_project_std(project_id, payload)

    def delete_project(self, project_id: str) -> bool:
        return services.delete_project_std(project_id)


# ---------------------------------------------------------------------------
# Remote (HTTP API) backend
# ---------------------------------------------------------------------------


class HttpTaskRepository:
    """Repository that proxies to a running ``systema2`` FastAPI server."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
        api_key: str | None = None,
    ):
        self._base_url = (base_url or get_api_url()).rstrip("/")
        self._timeout = timeout
        # ``api_key`` overrides env for tests / explicit wiring. Passing
        # an empty string disables auth regardless of env.
        self._api_key = api_key if api_key is not None else get_api_key()

    # --- helpers --------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {API_KEY_HEADER: self._api_key}
        return {}

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=self._headers(),
        )

    @staticmethod
    def _to_task(data: dict) -> Task:
        return Task.model_validate(data)

    @staticmethod
    def _to_project(data: dict) -> Project:
        return Project.model_validate(data)

    def _network_error(self, exc: httpx.HTTPError) -> RepositoryError:
        return RepositoryError(
            f"Could not reach systema2 server at {self._base_url}: {exc}"
        )

    @staticmethod
    def _maybe_auth_error(r: httpx.Response) -> None:
        """Translate 401/403 into :class:`AuthenticationError`."""
        if r.status_code not in (401, 403):
            return
        try:
            detail = r.json().get("detail", r.reason_phrase)
        except ValueError:
            detail = r.reason_phrase
        raise AuthenticationError(
            f"systema2 server rejected API key ({r.status_code}): {detail}"
        )

    def _maybe_project_error(self, r: httpx.Response) -> None:
        """Translate a 400 ``project_not_found`` into ProjectNotFoundError."""
        if r.status_code != 400:
            return
        try:
            detail = r.json().get("detail")
        except ValueError:
            return
        if (
            isinstance(detail, dict)
            and detail.get("error_code") == "project_not_found"
        ):
            raise ProjectNotFoundError(str(detail["project_id"]))

    # --- tasks ----------------------------------------------------------

    def list_tasks(
        self,
        *,
        project_id: str | None = None,
        unassigned: bool = False,
        priority: Priority | None = None,
        due_before: date | None = None,
    ) -> list[Task]:
        params: dict[str, object] = {}
        if unassigned:
            params["unassigned"] = "true"
        elif project_id is not None:
            params["project_id"] = project_id
        if priority is not None:
            params["priority"] = priority.value
        if due_before is not None:
            params["due_before"] = due_before.isoformat()
        try:
            with self._client() as c:
                r = c.get("/tasks", params=params)
                self._maybe_auth_error(r)
                r.raise_for_status()
                return [self._to_task(item) for item in r.json()]
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    def get_task(self, task_id: str) -> Task | None:
        try:
            with self._client() as c:
                r = c.get(f"/tasks/{task_id}")
                self._maybe_auth_error(r)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return self._to_task(r.json())
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    def create_task(self, payload: TaskCreate) -> Task:
        try:
            with self._client() as c:
                r = c.post("/tasks", json=payload.model_dump(mode="json"))
                self._maybe_auth_error(r)
                self._maybe_project_error(r)
                r.raise_for_status()
                return self._to_task(r.json())
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    def update_task(self, task_id: str, payload: TaskUpdate) -> Task | None:
        body = payload.model_dump(mode="json", exclude_unset=True)
        try:
            with self._client() as c:
                r = c.patch(f"/tasks/{task_id}", json=body)
                self._maybe_auth_error(r)
                if r.status_code == 404:
                    return None
                self._maybe_project_error(r)
                r.raise_for_status()
                return self._to_task(r.json())
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    def delete_task(self, task_id: str) -> bool:
        try:
            with self._client() as c:
                r = c.delete(f"/tasks/{task_id}")
                self._maybe_auth_error(r)
                if r.status_code == 404:
                    return False
                r.raise_for_status()
                return True
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    # --- projects -------------------------------------------------------

    def list_projects(self) -> list[Project]:
        try:
            with self._client() as c:
                r = c.get("/projects")
                self._maybe_auth_error(r)
                r.raise_for_status()
                return [self._to_project(item) for item in r.json()]
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    def get_project(self, project_id: str) -> Project | None:
        try:
            with self._client() as c:
                r = c.get(f"/projects/{project_id}")
                self._maybe_auth_error(r)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return self._to_project(r.json())
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    def create_project(self, payload: ProjectCreate) -> Project:
        try:
            with self._client() as c:
                r = c.post("/projects", json=payload.model_dump(mode="json"))
                self._maybe_auth_error(r)
                r.raise_for_status()
                return self._to_project(r.json())
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    def update_project(
        self, project_id: str, payload: ProjectUpdate
    ) -> Project | None:
        body = payload.model_dump(mode="json", exclude_unset=True)
        try:
            with self._client() as c:
                r = c.patch(f"/projects/{project_id}", json=body)
                self._maybe_auth_error(r)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return self._to_project(r.json())
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc

    def delete_project(self, project_id: str) -> bool:
        try:
            with self._client() as c:
                r = c.delete(f"/projects/{project_id}")
                self._maybe_auth_error(r)
                if r.status_code == 404:
                    return False
                r.raise_for_status()
                return True
        except httpx.HTTPError as exc:
            raise self._network_error(exc) from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_repository() -> TaskRepository:
    """Return the repository appropriate for the current mode."""
    mode = get_mode()
    if mode is Mode.CLIENT:
        return HttpTaskRepository()
    return LocalTaskRepository()
