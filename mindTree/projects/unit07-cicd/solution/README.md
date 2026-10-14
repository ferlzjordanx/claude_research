# Unit 7 Project — Pipeline for a FastAPI Service

A tiny pricing API (`/health`, `/version`, `/quote`) and everything
needed to ship it safely: a GitHub Actions workflow, an equivalent
Jenkinsfile, a post-deploy smoke test, a semantic-version helper
and policy tests that keep the pipeline honest.

```
PR:   lint ─┐
      type ─┼─► (stop: checks only)
      test ─┘  (3.12 + 3.13 matrix, JUnit artifacts)
main: checks ─► build+scan ─► push to ECR (OIDC) ─► staging
      ─► smoke test (rollback on failure) ─► approval ─► production
```

## Run the service

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory --reload
curl -s localhost:8000/version
```

## Run the pipeline checks locally

```bash
ruff check . && ruff format --check . && mypy && pytest -q
python -m scripts.smoke_test --base-url http://localhost:8000 \
    --expected-sha local --attempts 3 --delay 1
git log --format=%B%x00 v1.4.0..HEAD \
    | python -m scripts.next_version v1.4.0
```

Optional external tools: `actionlint` lints the workflow,
`act` runs GitHub Actions jobs locally in Docker, and
`docker build --build-arg GIT_SHA=$(git rev-parse HEAD) .` builds
the image (needs a Docker daemon).

## Configure the real pipeline (placeholders)

| Kind | Name | Example |
|------|------|---------|
| variable | `AWS_REGION` | `us-east-1` |
| variable | `AWS_CI_ROLE_ARN` | role that may push to ECR |
| variable | `AWS_DEPLOY_ROLE_ARN` | role mapped to EKS deploy access |
| variable | `ECR_REGISTRY` | `<acct>.dkr.ecr.<region>.amazonaws.com` |
| variable | `EKS_CLUSTER` | `apps-prod` |
| variable | `STAGING_URL`, `PRODUCTION_URL` | `https://...` |
| environment | `staging` | deployment branch: `main` |
| environment | `production` | required reviewers + `main` only |

No AWS access keys are stored anywhere: the roles trust GitHub's
OIDC provider, scoped to this repository and branch.

## Verify

`pytest -q` prints **63 passed**; ruff and mypy are clean.
