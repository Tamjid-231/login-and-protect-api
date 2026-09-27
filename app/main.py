"""FastAPI routes for the PostgreSQL-backed task service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from app import repository
from app.auth_routes import router as auth_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialize_database()
    yield


app = FastAPI(
    title="Login & Protect API",
    version="4.0.0",
    description="Week 4: Supabase signup, login, logout and verified bearer authentication. Paste the access token into Authorize to use the protected routes.",
    lifespan=lifespan,
)
app.include_router(auth_router)


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={'error': exc.detail}, headers=exc.headers)


class Task(BaseModel):
    id: int
    title: str
    done: bool


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str):
        if not value.strip():
            raise ValueError("title must not be empty")
        return value.strip()


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    done: StrictBool | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str | None):
        if value is not None and not value.strip():
            raise ValueError("title must not be empty")
        return value.strip() if value is not None else value


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]
    message = first_error.get("msg", "Invalid request body")
    return JSONResponse(status_code=400, content={"error": message})


@app.get("/", tags=["System"])
def api_information():
    return {
        "name": "Task API",
        "version": "4.0",
        "database": "PostgreSQL",
        "endpoints": ["/tasks", "/auth/signup", "/auth/login", "/auth/logout", "/protected/profile", "/protected/dashboard", "/public/info"],
    }


@app.get("/health", tags=["System"])
def health_check():
    if not repository.database_is_healthy():
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": "unavailable"},
        )
    return {"status": "ok", "db": "ok"}


@app.get("/tasks", response_model=list[Task], tags=["Tasks"])
def list_tasks():
    return repository.list_tasks()


@app.get("/tasks/{task_id}", response_model=Task, tags=["Tasks"])
def get_task(task_id: int):
    task = repository.get_task(task_id)
    if task is None:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return task


@app.post("/tasks", response_model=Task, status_code=201, tags=["Tasks"])
def create_task(task_data: TaskCreate):
    return repository.create_task(task_data.title)


@app.put("/tasks/{task_id}", response_model=Task, tags=["Tasks"])
def update_task(task_id: int, task_data: TaskUpdate):
    changes = task_data.model_dump(exclude_none=True)
    if not changes:
        return JSONResponse(
            status_code=400,
            content={"error": "Provide title and/or done"},
        )
    task = repository.update_task(
        task_id,
        title=changes.get("title"),
        done=changes.get("done"),
    )
    if task is None:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return task


@app.delete("/tasks/{task_id}", status_code=204, tags=["Tasks"])
def delete_task(task_id: int):
    if not repository.delete_task(task_id):
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return Response(status_code=204)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            responses = operation.get("responses", {})
            responses.pop("422", None)
            if method in {"post", "put"}:
                responses.setdefault("400", {"description": "Invalid request body"})
            if "{task_id}" in path:
                responses.setdefault("404", {"description": "Task not found"})
            if path.startswith('/auth/') or path.startswith('/protected/'):
                responses.setdefault('503', {'description': 'Authentication service unavailable'})
            if operation.get('security') or path == '/auth/login':
                responses.setdefault('401', {'description': 'Missing, malformed, invalid or expired credentials'})
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
