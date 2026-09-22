import pytest


def test_root_describes_postgres_api(client):
    assert client.get("/").json() == {
        "name": "Task API",
        "version": "3.0",
        "database": "PostgreSQL",
        "endpoints": ["/tasks"],
    }


def test_list_and_get_tasks(client):
    response = client.get("/tasks")
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert client.get("/tasks/1").json() == response.json()[0]


def test_create_update_delete_cycle(client):
    created = client.post("/tasks", json={"title": "Buy milk"})
    assert created.status_code == 201
    assert created.json() == {"id": 4, "title": "Buy milk", "done": False}

    task_id = created.json()["id"]
    updated = client.put(f"/tasks/{task_id}", json={"done": True})
    assert updated.status_code == 200
    assert updated.json() == {"id": task_id, "title": "Buy milk", "done": True}

    deleted = client.delete(f"/tasks/{task_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    missing = client.get(f"/tasks/{task_id}")
    assert missing.status_code == 404
    assert missing.json() == {"error": "Task not found"}


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}])
def test_create_rejects_missing_or_empty_title(client, body):
    response = client.post("/tasks", json=body)
    assert response.status_code == 400
    assert "error" in response.json()


def test_create_rejects_unknown_fields(client):
    response = client.post("/tasks", json={"title": "Valid", "done": True})
    assert response.status_code == 400
    assert "error" in response.json()


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"done": "yes"}, {"extra": 1}])
def test_update_rejects_invalid_body(client, body):
    response = client.put("/tasks/2", json=body)
    assert response.status_code == 400
    assert "error" in response.json()


def test_put_accepts_explicit_false(client):
    client.put("/tasks/1", json={"done": True})
    response = client.put("/tasks/1", json={"done": False})
    assert response.status_code == 200
    assert response.json()["done"] is False


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_unknown_task_returns_json_404(client, method):
    if method == "get":
        response = client.get("/tasks/999")
    elif method == "put":
        response = client.put("/tasks/999", json={"done": True})
    else:
        response = client.delete("/tasks/999")
    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_sql_looking_title_is_stored_literally(client):
    title = "Robert'); DROP TABLE tasks;--"
    response = client.post("/tasks", json={"title": title})
    assert response.status_code == 201
    assert response.json()["title"] == title
    assert len(client.get("/tasks").json()) == 4


def test_health_reports_database_status(client, fake_repository):
    assert client.get("/health").json() == {"status": "ok", "db": "ok"}
    fake_repository.healthy = False
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "unavailable"}


def test_openapi_documents_assignment_status_codes(client):
    schema = client.get("/openapi.json").json()
    assert "400" in schema["paths"]["/tasks"]["post"]["responses"]
    assert "422" not in schema["paths"]["/tasks"]["post"]["responses"]
    assert "404" in schema["paths"]["/tasks/{task_id}"]["get"]["responses"]
