from fastapi.testclient import TestClient
from sqlmodel import Session

from systema2.models import Task


def test_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"app": "systema2", "status": "ok"}


def test_list_tasks_empty(client: TestClient) -> None:
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_task(client: TestClient) -> None:
    response = client.post(
        "/tasks",
        json={"title": "write tests", "description": "cover endpoints"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["title"] == "write tests"
    assert data["description"] == "cover endpoints"
    assert data["completed"] is False
    assert "created_at" in data
    assert "updated_at" in data


def test_create_task_minimal(client: TestClient) -> None:
    response = client.post("/tasks", json={"title": "minimal"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "minimal"
    assert data["description"] is None
    assert data["completed"] is False


def test_create_task_validation_error(client: TestClient) -> None:
    # Empty title violates min_length=1
    response = client.post("/tasks", json={"title": ""})
    assert response.status_code == 422

    # Missing title
    response = client.post("/tasks", json={"description": "no title"})
    assert response.status_code == 422


def test_list_tasks_returns_created(client: TestClient) -> None:
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})

    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    titles = [t["title"] for t in data]
    assert titles == ["first", "second"]


def test_get_task(client: TestClient) -> None:
    created = client.post("/tasks", json={"title": "fetch me"}).json()
    task_id = created["id"]

    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "fetch me"


def test_get_task_not_found(client: TestClient) -> None:
    response = client.get("/tasks/9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_task(client: TestClient) -> None:
    created = client.post("/tasks", json={"title": "old title"}).json()
    task_id = created["id"]
    original_updated_at = created["updated_at"]

    response = client.patch(
        f"/tasks/{task_id}",
        json={"title": "new title", "completed": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "new title"
    assert data["completed"] is True
    assert data["description"] is None
    assert data["updated_at"] >= original_updated_at


def test_update_task_partial(client: TestClient) -> None:
    created = client.post(
        "/tasks", json={"title": "keep title", "description": "keep desc"}
    ).json()
    task_id = created["id"]

    response = client.patch(f"/tasks/{task_id}", json={"completed": True})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "keep title"
    assert data["description"] == "keep desc"
    assert data["completed"] is True


def test_update_task_empty_payload(client: TestClient) -> None:
    created = client.post("/tasks", json={"title": "unchanged"}).json()
    task_id = created["id"]

    response = client.patch(f"/tasks/{task_id}", json={})
    assert response.status_code == 200
    assert response.json()["title"] == "unchanged"


def test_update_task_not_found(client: TestClient) -> None:
    response = client.patch("/tasks/9999", json={"title": "nope"})
    assert response.status_code == 404


def test_delete_task(client: TestClient, session: Session) -> None:
    created = client.post("/tasks", json={"title": "delete me"}).json()
    task_id = created["id"]

    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 204
    assert response.content == b""

    # Confirm gone
    assert client.get(f"/tasks/{task_id}").status_code == 404
    assert session.get(Task, task_id) is None


def test_delete_task_not_found(client: TestClient) -> None:
    response = client.delete("/tasks/9999")
    assert response.status_code == 404
