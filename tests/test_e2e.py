"""End-to-end tests that spawn real ``systema2`` subprocesses.

Unlike the in-process CliRunner / TestClient tests, these exercise the full
packaging, entrypoint, argument parsing, network stack and DB file handling.

Covers all three modes:

- ``local``  : CLI writes to a SQLite file, CRUD persists across invocations.
- ``server`` : ``systema2 serve`` on an ephemeral port, hit with real HTTP.
- ``client`` : real CLI subprocess with ``SYSTEMA2_MODE=client`` talking to a
  real server subprocess.
"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from collections.abc import Generator, Sequence
from pathlib import Path

import httpx
import pytest

# The CLI is invoked as ``python -m systema2.cli`` so we don't depend on the
# console-script shim being on PATH.
CLI_ENTRY: list[str] = [sys.executable, "-m", "systema2.cli"]

# All tests in this module spawn real subprocesses — slow; opt out with
# ``pytest -m "not e2e"`` during fast iteration.
pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Return a currently-free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    result = subprocess.run(
        [*CLI_ENTRY, *args],
        cwd=cwd,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command {args!r} failed (rc={result.returncode}).\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def _wait_for_server(base_url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/", timeout=1.0)
            if r.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_exc = exc
        time.sleep(0.1)
    raise AssertionError(
        f"Server at {base_url} did not become ready in {timeout}s "
        f"(last error: {last_exc!r})"
    )


def _spawn_server(
    cwd: Path, port: int, mode: str = "server"
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.update({"SYSTEMA2_MODE": mode, "SYSTEMA2_PORT": str(port)})
    proc = subprocess.Popen(
        [*CLI_ENTRY, "serve", "--host", "127.0.0.1", "--port", str(port)],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


# SQLite helpers for local-mode tests (nano IDs are not predictable).
def _task_ids(db_path: Path) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT id FROM task ORDER BY created_at").fetchall()
    conn.close()
    return [r[0] for r in rows]


def _project_ids(db_path: Path) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT id FROM project ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _first_task_id(db_path: Path) -> str:
    ids = _task_ids(db_path)
    assert ids, "expected at least one task in the DB"
    return ids[0]


def _nth_task_id(db_path: Path, n: int) -> str:
    """Return the n-th task id (1-based)."""
    ids = _task_ids(db_path)
    assert len(ids) >= n, f"expected at least {n} tasks, got {len(ids)}"
    return ids[n - 1]


def _first_project_id(db_path: Path) -> str:
    ids = _project_ids(db_path)
    assert ids, "expected at least one project in the DB"
    return ids[0]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Isolated cwd so each test gets its own ``systema2.db``."""
    return tmp_path


@pytest.fixture
def server(
    workspace: Path,
) -> Generator[tuple[subprocess.Popen[str], str], None, None]:
    """Spawn a ``systema2 serve`` subprocess; yield (proc, base_url)."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = _spawn_server(workspace, port)
    try:
        _wait_for_server(base_url)
        yield proc, base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# Local mode
# ---------------------------------------------------------------------------


def test_e2e_local_crud_persists_across_invocations(workspace: Path) -> None:
    env = {"SYSTEMA2_MODE": "local"}

    # Start with an empty store.
    result = _run(["list"], cwd=workspace, env=env)
    assert "No tasks" in result.stdout

    _run(
        ["create", "buy milk", "-d", "2L semi-skimmed"],
        cwd=workspace,
        env=env,
    )
    _run(["create", "walk dog"], cwd=workspace, env=env)

    # DB file was created in the cwd.
    assert (workspace / "systema2.db").exists()

    # A completely new process still sees both tasks.
    result = _run(["list"], cwd=workspace, env=env)
    assert "buy milk" in result.stdout
    assert "walk dog" in result.stdout

    # Update + delete in fresh processes (discover IDs via SQLite).
    db = workspace / "systema2.db"
    t1 = _first_task_id(db)
    t2 = _nth_task_id(db, 2)
    _run(["update", t1, "--completed"], cwd=workspace, env=env)
    _run(["delete", t2, "--yes"], cwd=workspace, env=env)

    result = _run(["list"], cwd=workspace, env=env)
    assert "buy milk" in result.stdout
    assert "walk dog" not in result.stdout
    # Task #1 is marked completed (✓ glyph in the rendered table).
    assert "✓" in result.stdout


def test_e2e_local_update_not_found_exits_nonzero(workspace: Path) -> None:
    result = _run(
        ["update", "nonexistent", "-t", "ghost"],
        cwd=workspace,
        env={"SYSTEMA2_MODE": "local"},
        check=False,
    )
    assert result.returncode == 1
    assert "not found" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Server mode
# ---------------------------------------------------------------------------


def test_e2e_server_real_http_crud(
    server: tuple[subprocess.Popen[str], str],
) -> None:
    _proc, base_url = server

    # Root health check.
    r = httpx.get(f"{base_url}/", timeout=3.0)
    assert r.status_code == 200
    assert r.json() == {"app": "systema2", "status": "ok"}

    # Empty list.
    r = httpx.get(f"{base_url}/tasks", timeout=3.0)
    assert r.status_code == 200
    assert r.json() == []

    # Create.
    r = httpx.post(
        f"{base_url}/tasks",
        json={"title": "e2e task", "description": "via http"},
        timeout=3.0,
    )
    assert r.status_code == 201
    created = r.json()
    task_id = created["id"]
    assert created["title"] == "e2e task"
    assert created["completed"] is False

    # Partial update.
    r = httpx.patch(
        f"{base_url}/tasks/{task_id}",
        json={"completed": True},
        timeout=3.0,
    )
    assert r.status_code == 200
    assert r.json()["completed"] is True
    assert r.json()["title"] == "e2e task"  # unchanged

    # Get by id.
    r = httpx.get(f"{base_url}/tasks/{task_id}", timeout=3.0)
    assert r.status_code == 200

    # 404 for unknown id.
    r = httpx.get(f"{base_url}/tasks/nonexistent", timeout=3.0)
    assert r.status_code == 404

    # Delete.
    r = httpx.delete(f"{base_url}/tasks/{task_id}", timeout=3.0)
    assert r.status_code == 204

    # Confirm gone.
    r = httpx.get(f"{base_url}/tasks/{task_id}", timeout=3.0)
    assert r.status_code == 404


def test_e2e_server_writes_db_file(
    server: tuple[subprocess.Popen[str], str], workspace: Path
) -> None:
    _proc, base_url = server

    httpx.post(
        f"{base_url}/tasks",
        json={"title": "persisted"},
        timeout=3.0,
    ).raise_for_status()

    # The server was spawned with cwd=workspace, so the SQLite file lives there.
    assert (workspace / "systema2.db").exists()


# ---------------------------------------------------------------------------
# Client mode (real CLI subprocess → real server subprocess)
# ---------------------------------------------------------------------------


def test_e2e_client_round_trip_through_real_server(
    tmp_path: Path,
) -> None:
    # Keep server and client in separate cwds so we can verify the client
    # does not touch any local DB file.
    server_cwd = tmp_path / "server"
    client_cwd = tmp_path / "client"
    server_cwd.mkdir()
    client_cwd.mkdir()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = _spawn_server(server_cwd, port)
    try:
        _wait_for_server(base_url)

        client_env = {
            "SYSTEMA2_MODE": "client",
            "SYSTEMA2_API_URL": base_url,
        }

        # List is empty.
        r = _run(["list"], cwd=client_cwd, env=client_env)
        assert "No tasks" in r.stdout

        # Create via client → should hit the server.
        _run(
            ["create", "remote task", "-d", "via client"],
            cwd=client_cwd,
            env=client_env,
        )

        # Client sees its own write.
        r = _run(["list"], cwd=client_cwd, env=client_env)
        assert "remote task" in r.stdout
        assert "via client" in r.stdout

        # Server's REST API also sees it — proves it really went over HTTP.
        tasks = httpx.get(f"{base_url}/tasks", timeout=3.0).json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "remote task"

        # Update + delete via client.
        _run(
            ["update", str(tasks[0]["id"]), "--completed"],
            cwd=client_cwd,
            env=client_env,
        )
        tasks = httpx.get(f"{base_url}/tasks", timeout=3.0).json()
        assert tasks[0]["completed"] is True

        _run(
            ["delete", str(tasks[0]["id"]), "--yes"],
            cwd=client_cwd,
            env=client_env,
        )
        assert httpx.get(f"{base_url}/tasks", timeout=3.0).json() == []

        # Client cwd must not contain a systema2.db — client mode never
        # initializes the local database.
        assert not (client_cwd / "systema2.db").exists()
        # But the server's cwd does.
        assert (server_cwd / "systema2.db").exists()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_e2e_client_unreachable_server_exits_2(tmp_path: Path) -> None:
    # Port 1 is privileged and not listening → connection refused.
    result = _run(
        ["list"],
        cwd=tmp_path,
        env={
            "SYSTEMA2_MODE": "client",
            "SYSTEMA2_API_URL": "http://127.0.0.1:1",
        },
        check=False,
    )
    assert result.returncode == 2
    assert "Could not reach" in result.stdout


def test_e2e_invalid_mode_fails(tmp_path: Path) -> None:
    result = _run(
        ["list"],
        cwd=tmp_path,
        env={"SYSTEMA2_MODE": "bogus"},
        check=False,
    )
    assert result.returncode != 0
    # ValueError from config.get_mode() is surfaced in the traceback.
    combined = result.stdout + result.stderr
    assert "Invalid SYSTEMA2_MODE" in combined


def test_e2e_json_via_api_matches_schema(
    server: tuple[subprocess.Popen[str], str],
) -> None:
    """The task payload returned by the server must match TaskRead."""
    _proc, base_url = server
    created = httpx.post(
        f"{base_url}/tasks",
        json={"title": "schema check"},
        timeout=3.0,
    ).json()
    expected_keys = {
        "id",
        "title",
        "description",
        "completed",
        "priority",
        "due_date",
        "project_id",
        "created_at",
        "updated_at",
    }
    assert set(created.keys()) == expected_keys
    # Timestamps should be ISO-8601 strings parseable by json round-trip.
    json.dumps(created)  # no non-serializable values


# ---------------------------------------------------------------------------
# Projects — local mode
# ---------------------------------------------------------------------------


def test_e2e_local_project_lifecycle(workspace: Path) -> None:
    env = {"SYSTEMA2_MODE": "local"}
    db = workspace / "systema2.db"

    # Create a project and a task linked to it.
    _run(["project", "create", "work", "-d", "desk"], cwd=workspace, env=env)
    pid = _first_project_id(db)
    _run(["create", "deep work", "-p", pid], cwd=workspace, env=env)
    _run(["create", "orphan"], cwd=workspace, env=env)

    # Project listing.
    r = _run(["project", "list"], cwd=workspace, env=env)
    assert "work" in r.stdout

    # Filtering.
    r = _run(["list", "-p", pid], cwd=workspace, env=env)
    assert "deep work" in r.stdout
    assert "orphan" not in r.stdout

    r = _run(["list", "--unassigned"], cwd=workspace, env=env)
    assert "orphan" in r.stdout
    assert "deep work" not in r.stdout

    # Missing project => exit 1.
    r = _run(
        ["create", "bad", "-p", "nonexistent"],
        cwd=workspace,
        env=env,
        check=False,
    )
    assert r.returncode == 1
    assert "Project nonexistent not found" in r.stdout

    # Deleting the project unlinks tasks across subprocess boundaries.
    _run(["project", "delete", pid, "--yes"], cwd=workspace, env=env)
    r = _run(["list", "--unassigned"], cwd=workspace, env=env)
    assert "deep work" in r.stdout
    assert "orphan" in r.stdout


# ---------------------------------------------------------------------------
# Projects — server & client modes
# ---------------------------------------------------------------------------


def test_e2e_server_project_http_crud(
    server: tuple[subprocess.Popen[str], str],
) -> None:
    _proc, base_url = server

    # Create a project.
    r = httpx.post(
        f"{base_url}/projects", json={"name": "P"}, timeout=3.0
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    # Create tasks, one in the project and one outside.
    r = httpx.post(
        f"{base_url}/tasks",
        json={"title": "inside", "project_id": pid},
        timeout=3.0,
    )
    assert r.status_code == 201
    assert r.json()["project_id"] == pid
    httpx.post(
        f"{base_url}/tasks", json={"title": "outside"}, timeout=3.0
    ).raise_for_status()

    # Filtering over real HTTP.
    r = httpx.get(
        f"{base_url}/tasks", params={"project_id": pid}, timeout=3.0
    )
    titles = [t["title"] for t in r.json()]
    assert titles == ["inside"]

    r = httpx.get(
        f"{base_url}/tasks", params={"unassigned": "true"}, timeout=3.0
    )
    titles = [t["title"] for t in r.json()]
    assert titles == ["outside"]

    # Nested route.
    r = httpx.get(f"{base_url}/projects/{pid}/tasks", timeout=3.0)
    assert [t["title"] for t in r.json()] == ["inside"]

    # Deleting the project unlinks tasks (through the HTTP layer).
    r = httpx.delete(f"{base_url}/projects/{pid}", timeout=3.0)
    assert r.status_code == 204

    tasks = httpx.get(f"{base_url}/tasks", timeout=3.0).json()
    assert all(t["project_id"] is None for t in tasks)


def test_e2e_client_project_round_trip(tmp_path: Path) -> None:
    server_cwd = tmp_path / "server"
    client_cwd = tmp_path / "client"
    server_cwd.mkdir()
    client_cwd.mkdir()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = _spawn_server(server_cwd, port)
    try:
        _wait_for_server(base_url)
        env = {"SYSTEMA2_MODE": "client", "SYSTEMA2_API_URL": base_url}

        # Create project + linked task via the client CLI.
        _run(["project", "create", "work"], cwd=client_cwd, env=env)
        # Discover the project ID from the server API.
        projects = httpx.get(f"{base_url}/projects", timeout=3.0).json()
        assert len(projects) == 1
        pid = projects[0]["id"]

        _run(["create", "deep work", "-p", pid], cwd=client_cwd, env=env)

        # Verify through the REST API directly.
        tasks = httpx.get(f"{base_url}/tasks", timeout=3.0).json()
        assert len(tasks) == 1
        assert tasks[0]["project_id"] == pid

        # Client-side filtering.
        r = _run(["list", "-p", pid], cwd=client_cwd, env=env)
        assert "deep work" in r.stdout

        # Deleting through the client unlinks tasks server-side.
        _run(
            ["project", "delete", pid, "--yes"], cwd=client_cwd, env=env
        )
        tasks = httpx.get(f"{base_url}/tasks", timeout=3.0).json()
        assert len(tasks) == 1
        assert tasks[0]["project_id"] is None

        # Client never wrote a local DB.
        assert not (client_cwd / "systema2.db").exists()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# Priority — end-to-end
# ---------------------------------------------------------------------------


def test_e2e_local_priority_round_trip(workspace: Path) -> None:
    env = {"SYSTEMA2_MODE": "local"}
    db = workspace / "systema2.db"

    _run(["create", "urgent", "-P", "H"], cwd=workspace, env=env)
    _run(["create", "normal"], cwd=workspace, env=env)
    _run(["create", "whenever", "-P", "L"], cwd=workspace, env=env)

    r = _run(["list", "-P", "H"], cwd=workspace, env=env)
    assert "urgent" in r.stdout
    assert "normal" not in r.stdout
    assert "whenever" not in r.stdout

    # Update priority on a fresh subprocess.
    t2 = _nth_task_id(db, 2)
    _run(["update", t2, "-P", "H"], cwd=workspace, env=env)
    r = _run(["list", "-P", "H"], cwd=workspace, env=env)
    assert "urgent" in r.stdout
    assert "normal" in r.stdout

    # Invalid priority -> non-zero exit from Typer's enum validation.
    r = _run(
        ["create", "bad", "-P", "X"],
        cwd=workspace,
        env=env,
        check=False,
    )
    assert r.returncode != 0


def test_e2e_client_priority_round_trip(tmp_path: Path) -> None:
    server_cwd = tmp_path / "server"
    client_cwd = tmp_path / "client"
    server_cwd.mkdir()
    client_cwd.mkdir()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = _spawn_server(server_cwd, port)
    try:
        _wait_for_server(base_url)
        env = {"SYSTEMA2_MODE": "client", "SYSTEMA2_API_URL": base_url}

        _run(["create", "urgent", "-P", "H"], cwd=client_cwd, env=env)
        _run(["create", "plain"], cwd=client_cwd, env=env)

        # Verify via the API directly.
        tasks = httpx.get(
            f"{base_url}/tasks", timeout=3.0
        ).json()
        prios = {t["title"]: t["priority"] for t in tasks}
        assert prios == {"urgent": "H", "plain": "M"}

        # Filter via the client.
        r = _run(["list", "-P", "H"], cwd=client_cwd, env=env)
        assert "urgent" in r.stdout
        assert "plain" not in r.stdout

        # Client never wrote a local DB.
        assert not (client_cwd / "systema2.db").exists()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# Due dates — end-to-end
# ---------------------------------------------------------------------------


def test_e2e_local_due_date_round_trip(workspace: Path) -> None:
    env = {"SYSTEMA2_MODE": "local"}
    db = workspace / "systema2.db"

    _run(
        ["create", "early", "-D", "2030-01-01"],
        cwd=workspace,
        env=env,
    )
    _run(
        ["create", "late", "-D", "2030-12-31"],
        cwd=workspace,
        env=env,
    )
    _run(["create", "no-date"], cwd=workspace, env=env)

    # Filter by due-before.
    r = _run(
        ["list", "--due-before", "2030-06-01"], cwd=workspace, env=env
    )
    assert "early" in r.stdout
    assert "late" not in r.stdout
    assert "no-date" not in r.stdout

    # Set a due date on the no-date task in a fresh process.
    t3 = _nth_task_id(db, 3)
    _run(
        ["update", t3, "-D", "2029-01-01"], cwd=workspace, env=env
    )
    r = _run(
        ["list", "--due-before", "2029-06-01"], cwd=workspace, env=env
    )
    assert "no-date" in r.stdout

    # Clear the due date.
    _run(["update", t3, "--clear-due"], cwd=workspace, env=env)
    r = _run(
        ["list", "--due-before", "2029-06-01"], cwd=workspace, env=env
    )
    assert "no-date" not in r.stdout

    # Invalid date input -> exit 2.
    r = _run(
        ["create", "bad", "-D", "tomorrow"],
        cwd=workspace,
        env=env,
        check=False,
    )
    assert r.returncode == 2


def test_e2e_client_due_date_round_trip(tmp_path: Path) -> None:
    server_cwd = tmp_path / "server"
    client_cwd = tmp_path / "client"
    server_cwd.mkdir()
    client_cwd.mkdir()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = _spawn_server(server_cwd, port)
    try:
        _wait_for_server(base_url)
        env = {"SYSTEMA2_MODE": "client", "SYSTEMA2_API_URL": base_url}

        _run(
            ["create", "deadline", "-D", "2030-07-04"],
            cwd=client_cwd,
            env=env,
        )
        _run(["create", "someday"], cwd=client_cwd, env=env)

        # Verify via the API directly.
        tasks = httpx.get(f"{base_url}/tasks", timeout=3.0).json()
        due = {t["title"]: t["due_date"] for t in tasks}
        assert due == {"deadline": "2030-07-04", "someday": None}

        # Filter via the client CLI.
        r = _run(
            ["list", "--due-before", "2030-12-31"],
            cwd=client_cwd,
            env=env,
        )
        assert "deadline" in r.stdout
        assert "someday" not in r.stdout

        # Clear via the client CLI.
        deadline_task = next(t for t in tasks if t["title"] == "deadline")
        _run(
            ["update", deadline_task["id"], "--clear-due"],
            cwd=client_cwd,
            env=env,
        )
        tasks = httpx.get(f"{base_url}/tasks", timeout=3.0).json()
        assert all(t["due_date"] is None for t in tasks)

        assert not (client_cwd / "systema2.db").exists()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_e2e_client_missing_project_exits_1(tmp_path: Path) -> None:
    server_cwd = tmp_path / "server"
    client_cwd = tmp_path / "client"
    server_cwd.mkdir()
    client_cwd.mkdir()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = _spawn_server(server_cwd, port)
    try:
        _wait_for_server(base_url)
        result = _run(
            ["create", "x", "-p", "nonexistent"],
            cwd=client_cwd,
            env={"SYSTEMA2_MODE": "client", "SYSTEMA2_API_URL": base_url},
            check=False,
        )
        assert result.returncode == 1
        assert "Project nonexistent not found" in result.stdout
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
