from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def load_compose() -> dict:
    return yaml.safe_load(read("compose.yaml"))


def test_env_is_ignored_and_example_documents_every_key():
    gitignore = read(".gitignore").splitlines()
    example = read(".env.example")
    assert ".env" in gitignore
    assert "docs/superpowers/" in gitignore
    assert "POSTGRES_USER=postgres" in example
    assert "POSTGRES_PASSWORD=dev" in example
    assert "POSTGRES_DB=tasks" in example
    assert "DATABASE_URL=postgresql://postgres:dev@db:5432/tasks" in example
    # A developer needs a local .env; the requirement is that Git excludes it.
    import subprocess
    result = subprocess.run(['git', 'check-ignore', '.env'], cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert result.returncode == 0


def test_compose_starts_api_and_healthy_database_with_named_volume():
    compose = load_compose()
    assert set(compose["services"]) == {"api", "db"}
    assert compose["services"]["api"]["ports"] == ["3000:3000"]
    assert "db:5432" in read(".env.example")
    assert compose["services"]["api"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert compose["services"]["db"]["volumes"] == [
        "taskdata:/var/lib/postgresql/data"
    ]
    assert compose["services"]["db"]["healthcheck"]["test"][0] == "CMD-SHELL"
    assert "taskdata" in compose["volumes"]


def test_compose_uses_environment_interpolation_and_no_source_mount():
    compose = load_compose()
    api = compose["services"]["api"]
    db = compose["services"]["db"]
    assert "volumes" not in api
    assert db["environment"]["POSTGRES_USER"] == "${POSTGRES_USER}"
    assert db["environment"]["POSTGRES_PASSWORD"] == "${POSTGRES_PASSWORD}"
    assert db["environment"]["POSTGRES_DB"] == "${POSTGRES_DB}"
    assert api["environment"]["DATABASE_URL"] == "${DATABASE_URL}"


def test_compose_api_healthcheck_calls_the_public_health_endpoint():
    api = load_compose()["services"]["api"]
    healthcheck = api["healthcheck"]

    assert healthcheck["test"] == [
        "CMD",
        "python",
        "-c",
        (
            "import urllib.request; "
            "urllib.request.urlopen('http://localhost:3000/health', timeout=3)"
        ),
    ]
    assert healthcheck["interval"] == "10s"
    assert healthcheck["timeout"] == "5s"
    assert healthcheck["retries"] == 5


def test_dockerfile_runs_non_root_api_on_port_3000():
    dockerfile = read("Dockerfile")
    assert dockerfile.startswith("FROM python:3.12-slim")
    assert "USER appuser" in dockerfile
    assert "EXPOSE 3000" in dockerfile
    assert '"uvicorn", "app.main:app"' in dockerfile
    assert '"--host", "0.0.0.0", "--port", "3000"' in dockerfile


def test_docker_context_excludes_secrets_and_generated_files():
    excluded = read(".dockerignore").splitlines()
    assert ".env" in excluded
    assert ".venv" in excluded
    assert "__pycache__" in excluded
    assert ".pytest_cache" in excluded
    assert ".git" in excluded


def test_ci_workflow_installs_dependencies_and_runs_the_test_suite():
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "tests.yml"
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["test"]["steps"]
    uses = [step.get("uses", "") for step in steps]
    commands = "\n".join(step.get("run", "") for step in steps)

    assert any(item.startswith("actions/checkout@") for item in uses)
    assert any(item.startswith("actions/setup-python@") for item in uses)
    assert "pip install -r requirements-dev.txt" in commands
    assert "python -m pytest -q" in commands
