"""HTTP API tests for projects and project-linked tasks."""

from __future__ import annotations

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


def test_list_projects_empty(client: TestClient) -> None:
    r = client.get("/projects")
    assert r.status_code == 200
    assert r.json() == []


def test_create_project(client: TestClient) -> None:
    r = client.post("/projects", json={"name": "home", "description": "chores"})
    assert r.status_code == 201
    data = r.json()
    assert data["id"] is not None
    assert data["name"] == "home"
    assert data["description"] == "chores"
    assert "created_at" in data
    assert "updated_at" in data


def test_create_project_validation(client: TestClient) -> None:
    r = client.post("/projects", json={"name": ""})
    assert r.status_code == 422
    r = client.post("/projects", json={})
    assert r.status_code == 422


def test_get_project(client: TestClient) -> None:
    created = client.post("/projects", json={"name": "work"}).json()
    r = client.get(f"/projects/{created['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "work"


def test_get_project_not_found(client: TestClient) -> None:
    r = client.get("/projects/999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Project not found"


def test_update_project(client: TestClient) -> None:
    pid = client.post("/projects", json={"name": "old"}).json()["id"]
    r = client.patch(f"/projects/{pid}", json={"name": "new"})
    assert r.status_code == 200
    assert r.json()["name"] == "new"


def test_update_project_partial_preserves_name(client: TestClient) -> None:
    pid = client.post(
        "/projects", json={"name": "keep", "description": "old"}
    ).json()["id"]
    r = client.patch(f"/projects/{pid}", json={"description": "new desc"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "keep"
    assert data["description"] == "new desc"


def test_update_project_not_found(client: TestClient) -> None:
    r = client.patch("/projects/999", json={"name": "x"})
    assert r.status_code == 404


def test_delete_project_unlinks_tasks(client: TestClient) -> None:
    pid = client.post("/projects", json={"name": "doomed"}).json()["id"]
    # Create two tasks in the project and one outside it.
    t_in1 = client.post(
        "/tasks", json={"title": "in1", "project_id": pid}
    ).json()["id"]
    t_in2 = client.post(
        "/tasks", json={"title": "in2", "project_id": pid}
    ).json()["id"]
    t_out = client.post("/tasks", json={"title": "out"}).json()["id"]

    r = client.delete(f"/projects/{pid}")
    assert r.status_code == 204

    # Project gone.
    assert client.get(f"/projects/{pid}").status_code == 404

    # Tasks survive but are unassigned.
    for tid in (t_in1, t_in2, t_out):
        task = client.get(f"/tasks/{tid}").json()
        assert task["project_id"] is None


def test_delete_project_not_found(client: TestClient) -> None:
    r = client.delete("/projects/999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tasks ↔ projects
# ---------------------------------------------------------------------------


def test_create_task_with_project(client: TestClient) -> None:
    pid = client.post("/projects", json={"name": "P"}).json()["id"]
    r = client.post("/tasks", json={"title": "T", "project_id": pid})
    assert r.status_code == 201
    assert r.json()["project_id"] == pid


def test_create_task_with_missing_project_400(client: TestClient) -> None:
    r = client.post("/tasks", json={"title": "T", "project_id": 999})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error_code"] == "project_not_found"
    assert detail["project_id"] == 999


def test_update_task_change_project(client: TestClient) -> None:
    p1 = client.post("/projects", json={"name": "p1"}).json()["id"]
    p2 = client.post("/projects", json={"name": "p2"}).json()["id"]
    tid = client.post(
        "/tasks", json={"title": "T", "project_id": p1}
    ).json()["id"]

    r = client.patch(f"/tasks/{tid}", json={"project_id": p2})
    assert r.status_code == 200
    assert r.json()["project_id"] == p2


def test_update_task_clear_project(client: TestClient) -> None:
    pid = client.post("/projects", json={"name": "p"}).json()["id"]
    tid = client.post(
        "/tasks", json={"title": "T", "project_id": pid}
    ).json()["id"]

    r = client.patch(f"/tasks/{tid}", json={"project_id": None})
    assert r.status_code == 200
    assert r.json()["project_id"] is None


def test_update_task_missing_project_400(client: TestClient) -> None:
    tid = client.post("/tasks", json={"title": "T"}).json()["id"]
    r = client.patch(f"/tasks/{tid}", json={"project_id": 999})
    assert r.status_code == 400
    assert r.json()["detail"]["error_code"] == "project_not_found"


def test_list_tasks_filter_by_project(client: TestClient) -> None:
    p1 = client.post("/projects", json={"name": "p1"}).json()["id"]
    p2 = client.post("/projects", json={"name": "p2"}).json()["id"]
    client.post("/tasks", json={"title": "a", "project_id": p1})
    client.post("/tasks", json={"title": "b", "project_id": p1})
    client.post("/tasks", json={"title": "c", "project_id": p2})
    client.post("/tasks", json={"title": "orphan"})

    r = client.get("/tasks", params={"project_id": p1})
    titles = sorted(t["title"] for t in r.json())
    assert titles == ["a", "b"]

    r = client.get("/tasks", params={"project_id": p2})
    titles = [t["title"] for t in r.json()]
    assert titles == ["c"]


def test_list_tasks_unassigned(client: TestClient) -> None:
    pid = client.post("/projects", json={"name": "p"}).json()["id"]
    client.post("/tasks", json={"title": "in", "project_id": pid})
    client.post("/tasks", json={"title": "out1"})
    client.post("/tasks", json={"title": "out2"})

    r = client.get("/tasks", params={"unassigned": "true"})
    assert r.status_code == 200
    titles = sorted(t["title"] for t in r.json())
    assert titles == ["out1", "out2"]


def test_list_project_tasks(client: TestClient) -> None:
    pid = client.post("/projects", json={"name": "p"}).json()["id"]
    client.post("/tasks", json={"title": "a", "project_id": pid})
    client.post("/tasks", json={"title": "b"})

    r = client.get(f"/projects/{pid}/tasks")
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert titles == ["a"]


def test_list_project_tasks_not_found(client: TestClient) -> None:
    r = client.get("/projects/999/tasks")
    assert r.status_code == 404
