"""Dockerfile, .dockerignore and compose rules, checked statically."""

from tests.manifests import ROOT, compose, final_cmd, stages


def test_dockerfile_is_multi_stage() -> None:
    all_stages = stages()
    assert len(all_stages) >= 2
    froms = [
        args for stage in all_stages for i, args in stage if i == "FROM"
    ]
    assert any(" AS builder" in f for f in froms)
    # The runtime stage copies artifacts from the builder, not sources
    # plus compilers.
    runtime = all_stages[-1]
    assert any(i == "COPY" and "--from=builder" in a for i, a in runtime)


def test_base_image_is_slim_and_pinned() -> None:
    text = (ROOT / "Dockerfile").read_text()
    assert "python:3.13-slim" in text
    assert ":latest" not in text


def test_final_stage_runs_as_non_root() -> None:
    users = [a for i, a in stages()[-1] if i == "USER"]
    assert users, "final stage has no USER"
    user = users[-1].split(":")[0]
    assert user not in {"root", "0"}
    # Numeric, so Kubernetes runAsNonRoot can verify it.
    assert user.isdigit()


def test_cmd_is_exec_form_with_factory_and_graceful_shutdown() -> None:
    cmd = final_cmd()
    assert cmd[0] == "uvicorn"
    assert "--factory" in cmd
    assert "--timeout-graceful-shutdown" in cmd
    assert cmd[cmd.index("--host") + 1] == "0.0.0.0"


def test_port_is_exposed() -> None:
    assert ("EXPOSE", "8000") in stages()[-1]


def test_dockerignore_keeps_secrets_and_junk_out() -> None:
    lines = (ROOT / ".dockerignore").read_text().splitlines()
    for entry in (".git", ".venv", ".env", "__pycache__"):
        assert entry in lines


def test_compose_waits_for_a_healthy_database() -> None:
    services = compose()["services"]
    assert "healthcheck" in services["db"]
    assert services["db"]["image"] == "postgres:18"
    depends = services["api"]["depends_on"]["db"]
    assert depends["condition"] == "service_healthy"


def test_compose_api_uses_postgres_via_env() -> None:
    env = compose()["services"]["api"]["environment"]
    assert env["APP_DATABASE_URL"].startswith("postgresql+psycopg://")
    assert "@db:5432/" in env["APP_DATABASE_URL"]
