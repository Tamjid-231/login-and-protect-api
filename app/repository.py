"""PostgreSQL persistence for the task API.

This is the only application module that contains SQL.
"""

from __future__ import annotations

import os
import time

import psycopg


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE
)
"""
COUNT_TASKS_SQL = "SELECT COUNT(*) FROM tasks"
INSERT_SEED_SQL = "INSERT INTO tasks (title, done) VALUES (%s, %s)"
LIST_TASKS_SQL = "SELECT id, title, done FROM tasks ORDER BY id"
GET_TASK_SQL = "SELECT id, title, done FROM tasks WHERE id = %s"
INSERT_TASK_SQL = (
    "INSERT INTO tasks (title, done) VALUES (%s, %s) "
    "RETURNING id, title, done"
)
UPDATE_TASK_SQL = (
    "UPDATE tasks SET title = %s, done = %s WHERE id = %s "
    "RETURNING id, title, done"
)
DELETE_TASK_SQL = "DELETE FROM tasks WHERE id = %s RETURNING id"
HEALTH_SQL = "SELECT 1"

SEED_TASKS = (
    ("Read the assignment", True),
    ("Connect the API to PostgreSQL", False),
    ("Test database persistence", False),
)


def get_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return database_url


def _row_to_task(row: tuple | None) -> dict | None:
    if row is None:
        return None
    return {"id": row[0], "title": row[1], "done": bool(row[2])}


def initialize_database(max_attempts: int = 10, delay_seconds: float = 1.0) -> None:
    database_url = get_database_url()
    for attempt in range(1, max_attempts + 1):
        try:
            with psycopg.connect(database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(CREATE_TABLE_SQL)
                    cursor.execute(COUNT_TASKS_SQL)
                    count = cursor.fetchone()[0]
                    if count == 0:
                        cursor.executemany(INSERT_SEED_SQL, SEED_TASKS)
                connection.commit()
            return
        except psycopg.OperationalError:
            if attempt == max_attempts:
                raise
            time.sleep(delay_seconds)


def database_is_healthy() -> bool:
    try:
        with psycopg.connect(get_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(HEALTH_SQL)
                return cursor.fetchone() == (1,)
    except (psycopg.Error, RuntimeError):
        return False


def list_tasks() -> list[dict]:
    with psycopg.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(LIST_TASKS_SQL)
            return [_row_to_task(row) for row in cursor.fetchall()]


def get_task(task_id: int) -> dict | None:
    with psycopg.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(GET_TASK_SQL, (task_id,))
            return _row_to_task(cursor.fetchone())


def create_task(title: str) -> dict:
    with psycopg.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(INSERT_TASK_SQL, (title, False))
            task = _row_to_task(cursor.fetchone())
        connection.commit()
    return task


def update_task(task_id: int, title: str | None, done: bool | None) -> dict | None:
    with psycopg.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(GET_TASK_SQL, (task_id,))
            current = _row_to_task(cursor.fetchone())
            if current is None:
                return None
            new_title = current["title"] if title is None else title
            new_done = current["done"] if done is None else done
            cursor.execute(UPDATE_TASK_SQL, (new_title, new_done, task_id))
            updated = _row_to_task(cursor.fetchone())
        connection.commit()
    return updated


def delete_task(task_id: int) -> bool:
    with psycopg.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DELETE_TASK_SQL, (task_id,))
            deleted = cursor.fetchone() is not None
        connection.commit()
    return deleted
