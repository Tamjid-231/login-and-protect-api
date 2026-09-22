from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient


class FakeRepository:
    def __init__(self):
        self.tasks = [
            {"id": 1, "title": "Read the assignment", "done": True},
            {"id": 2, "title": "Connect the API to PostgreSQL", "done": False},
            {"id": 3, "title": "Test database persistence", "done": False},
        ]
        self.next_id = 4
        self.healthy = True

    def initialize_database(self):
        return None

    def database_is_healthy(self):
        return self.healthy

    def list_tasks(self):
        return copy.deepcopy(self.tasks)

    def get_task(self, task_id):
        task = next((task for task in self.tasks if task["id"] == task_id), None)
        return copy.deepcopy(task)

    def create_task(self, title):
        task = {"id": self.next_id, "title": title, "done": False}
        self.next_id += 1
        self.tasks.append(task)
        return copy.deepcopy(task)

    def update_task(self, task_id, title, done):
        task = next((task for task in self.tasks if task["id"] == task_id), None)
        if task is None:
            return None
        if title is not None:
            task["title"] = title
        if done is not None:
            task["done"] = done
        return copy.deepcopy(task)

    def delete_task(self, task_id):
        task = next((task for task in self.tasks if task["id"] == task_id), None)
        if task is None:
            return False
        self.tasks.remove(task)
        return True


@pytest.fixture
def fake_repository(monkeypatch):
    from app import main

    fake = FakeRepository()
    monkeypatch.setattr(main.repository, "initialize_database", fake.initialize_database)
    monkeypatch.setattr(main.repository, "database_is_healthy", fake.database_is_healthy)
    monkeypatch.setattr(main.repository, "list_tasks", fake.list_tasks)
    monkeypatch.setattr(main.repository, "get_task", fake.get_task)
    monkeypatch.setattr(main.repository, "create_task", fake.create_task)
    monkeypatch.setattr(main.repository, "update_task", fake.update_task)
    monkeypatch.setattr(main.repository, "delete_task", fake.delete_task)
    return fake


@pytest.fixture
def client(fake_repository):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

