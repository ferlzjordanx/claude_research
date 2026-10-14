"""Policy tests: the pipeline definition is code, so test it.

These run in milliseconds on every PR and catch the mistakes that
reviewers miss: a deploy that no longer waits for tests, a token
with write access everywhere, a pasted access key.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.conftest import PROJECT_ROOT

WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
JENKINSFILE = PROJECT_ROOT / "Jenkinsfile"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
DEPLOY_JOBS = ("deploy-staging", "deploy-production")
# Jobs allowed to request an OIDC token (they talk to AWS).
OIDC_JOBS = {"build", *DEPLOY_JOBS}


@pytest.fixture(scope="module")
def workflow() -> dict[Any, Any]:
    data = yaml.safe_load(WORKFLOW.read_text())
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def jobs(workflow: dict[Any, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = workflow["jobs"]
    return result


def triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # GOTCHA: YAML 1.1 (PyYAML) reads the bare key `on` as the boolean
    # True, like yes/no/off. GitHub's parser treats it as the string
    # "on". So the triggers live under workflow[True] here.
    value = workflow.get("on", workflow.get(True))
    assert isinstance(value, dict), "workflow has no `on:` triggers"
    return value


def needs_of(job: dict[str, Any]) -> set[str]:
    needs = job.get("needs", [])
    return {needs} if isinstance(needs, str) else set(needs)


def all_upstream(name: str, jobs: dict[str, dict[str, Any]]) -> set[str]:
    """Every job that must finish before `name` (transitive needs)."""
    seen: set[str] = set()
    stack = list(needs_of(jobs[name]))
    while stack:
        current = stack.pop()
        if current not in seen:
            seen.add(current)
            stack.extend(needs_of(jobs[current]))
    return seen


def env_name(job: dict[str, Any]) -> str | None:
    env = job.get("environment")
    return env.get("name") if isinstance(env, dict) else env


# --- GitHub Actions --------------------------------------------------


def test_yaml_on_key_gotcha() -> None:
    assert yaml.safe_load("on: push") == {True: "push"}


def test_triggers_are_pull_request_and_push_to_main(
    workflow: dict[Any, Any],
) -> None:
    on = triggers(workflow)
    assert "pull_request" in on
    assert on["push"]["branches"] == ["main"]


def test_top_level_permissions_are_read_only(
    workflow: dict[Any, Any],
) -> None:
    assert workflow["permissions"] == {"contents": "read"}


def test_concurrency_is_set(workflow: dict[Any, Any]) -> None:
    concurrency = workflow["concurrency"]
    assert "github.ref" in concurrency["group"]
    assert "cancel-in-progress" in concurrency


def test_oidc_token_only_where_needed(
    workflow: dict[Any, Any], jobs: dict[str, dict[str, Any]]
) -> None:
    assert "id-token" not in workflow["permissions"]
    for name, job in jobs.items():
        perms = job.get("permissions", {})
        if perms.get("id-token") == "write":
            assert name in OIDC_JOBS, f"{name} should not mint OIDC"
    for name in OIDC_JOBS:
        assert jobs[name]["permissions"]["id-token"] == "write"


def test_no_job_requests_write_on_contents(
    jobs: dict[str, dict[str, Any]],
) -> None:
    for name, job in jobs.items():
        perms = job.get("permissions", {})
        assert perms.get("contents", "read") == "read", name


def test_build_and_deploys_depend_on_all_checks(
    jobs: dict[str, dict[str, Any]],
) -> None:
    for name in ("build", *DEPLOY_JOBS):
        upstream = all_upstream(name, jobs)
        assert {"lint", "typecheck", "test"} <= upstream, name


def test_production_after_staging_with_environment(
    jobs: dict[str, dict[str, Any]],
) -> None:
    prod = jobs["deploy-production"]
    assert "deploy-staging" in needs_of(prod)
    assert env_name(prod) == "production"
    assert env_name(jobs["deploy-staging"]) == "staging"


def test_deploys_only_run_on_main(
    jobs: dict[str, dict[str, Any]],
) -> None:
    for name in DEPLOY_JOBS:
        assert "refs/heads/main" in jobs[name]["if"], name


def test_deploys_promote_the_built_digest(
    jobs: dict[str, dict[str, Any]],
) -> None:
    assert "image" in jobs["build"]["outputs"]
    for name in DEPLOY_JOBS:
        assert "build" in needs_of(jobs[name])
        image = jobs[name]["env"]["IMAGE"]
        assert image == "${{ needs.build.outputs.image }}", name


def test_deploys_smoke_test_and_roll_back(
    jobs: dict[str, dict[str, Any]],
) -> None:
    for name in DEPLOY_JOBS:
        steps = jobs[name]["steps"]
        runs = [s.get("run", "") for s in steps]
        assert any("scripts.smoke_test" in r for r in runs), name
        rollback = [s for s in steps if "rollout undo" in s.get("run", "")]
        assert rollback, f"{name} has no rollback step"
        assert rollback[0]["if"] == "failure()"


def test_tests_run_on_a_python_matrix_and_upload_reports(
    jobs: dict[str, dict[str, Any]],
) -> None:
    test = jobs["test"]
    versions = test["strategy"]["matrix"]["python-version"]
    assert {"3.12", "3.13"} <= set(versions)
    uploads = [
        s
        for s in test["steps"]
        if str(s.get("uses", "")).startswith("actions/upload-artifact")
    ]
    assert uploads and uploads[0]["if"] == "always()"


def test_actions_are_pinned_to_a_version_or_sha(
    jobs: dict[str, dict[str, Any]],
) -> None:
    for job in jobs.values():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if uses is None or uses.startswith("./"):
                continue
            action, _, ref = uses.partition("@")
            assert ref, f"{action} is not pinned"
            assert ref not in {"main", "master", "latest"}, uses


def test_no_long_lived_aws_keys_anywhere() -> None:
    for path in (WORKFLOW, JENKINSFILE):
        text = path.read_text()
        assert not re.search(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b", text)
        assert "aws-access-key-id" not in text
        assert "AWS_SECRET_ACCESS_KEY" not in text


def test_every_job_has_a_timeout(
    jobs: dict[str, dict[str, Any]],
) -> None:
    for name, job in jobs.items():
        assert job.get("timeout-minutes"), name


# --- Jenkins and Docker ----------------------------------------------

JENKINS_STAGES = [
    "Lint",
    "Typecheck",
    "Test",
    "Build & Push",
    "Deploy Staging",
    "Smoke Test",
    "Approve Production",
    "Deploy Production",
]


def jenkins_stage_names() -> list[str]:
    text = JENKINSFILE.read_text()
    return re.findall(r"stage\('([^']+)'\)", text)


def test_jenkins_has_required_stages_in_order() -> None:
    names = [n for n in jenkins_stage_names() if n in JENKINS_STAGES]
    assert names == JENKINS_STAGES


def test_jenkins_approval_test_report_and_rollback() -> None:
    text = JENKINSFILE.read_text()
    assert re.search(r"input\s*\{[^}]*submitter", text)
    assert re.search(r"junit\s+'reports/", text)
    post = text[text.index("\n  post {") :]
    assert re.search(r"failure\s*\{[\s\S]*rollback\(", post)
    assert "rollout undo" in text


def test_jenkins_deploy_stages_only_on_main() -> None:
    text = JENKINSFILE.read_text()
    for stage in JENKINS_STAGES[3:]:
        block = text[text.index(f"stage('{stage}')") :][:300]
        assert "when { branch 'main' }" in block, stage


def test_dockerfile_runs_as_non_root_and_bakes_the_sha() -> None:
    text = DOCKERFILE.read_text()
    assert re.search(r"^USER\s+(?!root|0\b)\S+", text, re.MULTILINE)
    assert "ARG GIT_SHA" in text
    assert "APP_GIT_SHA=${GIT_SHA}" in text


def test_all_pipeline_files_fit_76_columns() -> None:
    files = [WORKFLOW, JENKINSFILE, DOCKERFILE]
    files += list(Path(PROJECT_ROOT).glob("**/*.py"))
    for path in files:
        if ".venv" in path.parts:
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            assert len(line) <= 76, f"{path.name}:{number}"
