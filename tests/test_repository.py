from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field

import pytest

from app import repository


@dataclass
class FakeCursor(AbstractContextManager):
    fetchone_values: list[tuple | None] = field(default_factory=list)
    fetchall_value: list[tuple] = field(default_factory=list)
    execute_calls: list[tuple[str, tuple | None]] = field(default_factory=list)
    executemany_calls: list[tuple[str, tuple]] = field(default_factory=list)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query: str, parameters: tuple | None = None):
        self.execute_calls.append((query, parameters))
        return self

    def executemany(self, query: str, parameters: tuple):
        self.executemany_calls.append((query, parameters))
        return self

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return self.fetchall_value


@dataclass
class FakeConnection(AbstractContextManager):
    fetchone_values: list[tuple | None] = field(default_factory=list)
    fetchall_value: list[tuple] = field(default_factory=list)
    committed: bool = False
    rolled_back: bool = False

    def __post_init__(self):
        self.cursor_instance = FakeCursor(self.fetchone_values, self.fetchall_value)

    @property
    def execute_calls(self):
        return self.cursor_instance.execute_calls

    @property
    def executemany_calls(self):
        return self.cursor_instance.executemany_calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def install_connection(monkeypatch, connection: FakeConnection):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(repository.psycopg, "connect", lambda _: connection)


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        repository.get_database_url()


def test_initialize_seeds_only_when_empty(monkeypatch):
    connection = FakeConnection(fetchone_values=[(0,)])
    install_connection(monkeypatch, connection)

    repository.initialize_database(max_attempts=1, delay_seconds=0)

    assert connection.executemany_calls == [
        (repository.INSERT_SEED_SQL, repository.SEED_TASKS)
    ]
    assert connection.committed is True


def test_initialize_does_not_seed_nonempty_table(monkeypatch):
    connection = FakeConnection(fetchone_values=[(3,)])
    install_connection(monkeypatch, connection)

    repository.initialize_database(max_attempts=1, delay_seconds=0)

    assert connection.executemany_calls == []


def test_initialize_retries_temporary_connection_failure(monkeypatch):
    connection = FakeConnection(fetchone_values=[(3,)])
    attempts = iter([repository.psycopg.OperationalError("not ready"), connection])
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")

    def connect(_):
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(repository.psycopg, "connect", connect)
    repository.initialize_database(max_attempts=2, delay_seconds=0)

    assert connection.committed is True


def test_list_tasks_maps_postgres_rows(monkeypatch):
    connection = FakeConnection(
        fetchall_value=[(1, "Read the assignment", True), (2, "Build API", False)]
    )
    install_connection(monkeypatch, connection)

    assert repository.list_tasks() == [
        {"id": 1, "title": "Read the assignment", "done": True},
        {"id": 2, "title": "Build API", "done": False},
    ]


def test_get_unknown_task_returns_none(monkeypatch):
    connection = FakeConnection(fetchone_values=[None])
    install_connection(monkeypatch, connection)
    assert repository.get_task(999) is None


def test_create_uses_parameterized_title(monkeypatch):
    title = "Robert'); DROP TABLE tasks;--"
    connection = FakeConnection(fetchone_values=[(4, title, False)])
    install_connection(monkeypatch, connection)

    assert repository.create_task(title) == {"id": 4, "title": title, "done": False}
    assert connection.execute_calls[-1] == (repository.INSERT_TASK_SQL, (title, False))
    assert connection.committed is True


def test_update_preserves_explicit_false(monkeypatch):
    connection = FakeConnection(
        fetchone_values=[(1, "Existing", True), (1, "Existing", False)]
    )
    install_connection(monkeypatch, connection)

    assert repository.update_task(1, title=None, done=False) == {
        "id": 1,
        "title": "Existing",
        "done": False,
    }
    assert connection.execute_calls[-1] == (
        repository.UPDATE_TASK_SQL,
        ("Existing", False, 1),
    )


def test_update_unknown_task_returns_none(monkeypatch):
    connection = FakeConnection(fetchone_values=[None])
    install_connection(monkeypatch, connection)
    assert repository.update_task(99, title="Missing", done=True) is None


def test_delete_reports_whether_row_existed(monkeypatch):
    found_connection = FakeConnection(fetchone_values=[(1,)])
    install_connection(monkeypatch, found_connection)
    assert repository.delete_task(1) is True

    missing_connection = FakeConnection(fetchone_values=[None])
    install_connection(monkeypatch, missing_connection)
    assert repository.delete_task(99) is False


def test_health_query_reports_database_availability(monkeypatch):
    healthy = FakeConnection(fetchone_values=[(1,)])
    install_connection(monkeypatch, healthy)
    assert repository.database_is_healthy() is True

    monkeypatch.setattr(
        repository.psycopg,
        "connect",
        lambda _: (_ for _ in ()).throw(repository.psycopg.OperationalError("down")),
    )
    assert repository.database_is_healthy() is False
