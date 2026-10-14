# Unit 7 — CI/CD and Git Workflows (GitHub Actions and Jenkins)

## 1. What This Unit Teaches

Writing the code is half the job. The other half is getting it to production safely, repeatedly and with evidence **[JD-Required: CI/CD pipelines, Git, automated testing, Jenkins and/or GitHub Actions]**. An FDE often inherits a customer's pipeline (frequently Jenkins) or builds a new one (frequently GitHub Actions), and is judged by whether a change can go out today without breaking anything. This unit teaches:

- Git workflows that keep `main` releasable: trunk-based development, short-lived branches, pull requests, protected branches, CODEOWNERS, conventional commits, tags and semantic versioning;
- the recovery tools: `revert` vs `reset`, `bisect`;
- continuous integration: fast feedback, stage order, caching, matrices, test reports, and a flaky-test policy;
- continuous delivery: environments, promoting one image digest, rolling/blue-green/canary, feature flags, smoke tests, rollback, and database migrations inside a pipeline;
- pipeline security: OIDC federation to AWS instead of stored keys, least privilege, action pinning, image scanning, SBOMs and provenance;
- GitHub Actions and declarative Jenkins side by side, plus how GitLab CI and Azure DevOps map to the same ideas;
- testing the pipeline itself with policy tests.

## 2. Mental Model

```text
 developer ── short-lived branch ── PR ──────────────────────────┐
                                    │ CI (minutes, every push)   │
                                    ▼                            │
            ┌─ lint ──┐                                          │
            ├─ type ──┼─► all green + review ─► merge to main    │
            └─ test ──┘   (branch protection)        │           │
              matrix, JUnit reports                  ▼           │
                                     CI again on main, then CD:  │
   build image ─► scan ─► push ECR  image@sha256:9f2c… (digest)  │
   (tag = git sha)   (OIDC role, no stored keys)     │           │
                                                     ▼           │
   staging: set image → rollout status → smoke test /version     │
            │ fail → kubectl rollout undo                        │
            ▼ pass                                               │
   production: approval gate → SAME digest → smoke → (undo)      │
                                                                 │
   /version says git_sha=9f2c…  ◄── proof the change is live ────┘
```

Three ideas carry the unit:

1. **Main is always releasable.** Small changes, merged often, behind automated checks. Anything that would break `main` is caught before merge.
2. **Build once, promote the same artifact.** The image tested in staging is byte-for-byte the image in production. You promote a digest; you never rebuild per environment.
3. **Every deploy verifies itself and can undo itself.** A smoke test proves the new commit is serving; a failure rolls back automatically and loudly.

## 3. Brief Theory

### 3.1 Branching models

**What it is.** A team agreement on how branches are created, named, merged and released.

**Why it exists.** Many people change one codebase. Without rules, merges become painful and nobody knows what is in production.

**Why it matters.** The branching model sets your release speed. Long-lived branches mean big, risky merges.

**How it works.**

| Model | Shape | Fits | Cost |
|---|---|---|---|
| Trunk-based **[Current]** | Branches live hours to a day or two, merge to `main` behind CI; unfinished work hidden by feature flags | SaaS, continuous delivery, most FDE projects | Needs good tests and flags |
| GitHub flow | Trunk-based with a PR per branch, deploy from `main` | Most teams on GitHub | Same |
| GitFlow **[Legacy for web services]** | `develop`, `feature/*`, `release/*`, `hotfix/*`, `main` | Versioned products with several supported releases (installed software, mobile) | Slow, merge-heavy, unclear "what is in prod" |
| Release branches | Trunk plus `release/1.4` cut for stabilization | Libraries, on-prem customer installs | Backports (cherry-pick) |

The research summarized in *Accelerate* and the DORA reports links short-lived branches and small batches to better delivery performance ([DORA: trunk-based development](https://dora.dev/capabilities/trunk-based-development/) **[External]**).

### 3.2 Pull requests, protection and ownership

**What it is.** A pull request (PR) proposes merging a branch. Branch protection or **rulesets** on `main` decide what a PR needs before merge.

**Why it matters.** It turns "please be careful" into enforced rules.

**How it works** ([GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) **[Provider-specific]**):

- required status checks (the CI jobs must be green);
- required reviews, with `CODEOWNERS` assigning owners by path (for example, `/.github/workflows/ @platform-team`, so pipeline changes need platform review);
- no direct pushes, no force pushes to `main`;
- "require branches to be up to date", or better a **merge queue**, which tests the PR as it will be merged with the latest `main`;
- optionally signed commits (GPG, SSH or S/MIME) so authorship is verifiable.

Good PR habits: small (under about 400 changed lines), one purpose, a description that says *why* and *how it was tested*, screenshots for UI.

### 3.3 Merge vs rebase, revert vs reset

| Command | What it does | Use it when |
|---|---|---|
| `git merge` | Joins histories with a merge commit; history is true but branchy | Integrating a shared branch |
| `git rebase main` | Replays your commits on top of `main`; linear history, new commit IDs | Updating *your own* unpublished branch |
| Squash merge | One commit per PR on `main` | Most trunk-based repos; the PR title becomes the commit message |
| `git revert <sha>` | New commit that undoes `<sha>`; history kept | Undoing anything already pushed or shared |
| `git reset --hard <sha>` | Moves the branch pointer, discarding commits | Only local, unpublished work |

Golden rule: never rewrite history others have pulled. On `main`, undo with `revert`. `git bisect` finds the commit that introduced a bug by binary search; `git bisect run pytest -q tests/test_pricing.py` automates it across hundreds of commits ([git-bisect](https://git-scm.com/docs/git-bisect)).

### 3.4 Conventional commits, tags and semver

**What it is.** [Conventional Commits](https://www.conventionalcommits.org/) **[External]** is a message format: `type(scope)!: summary`, with types such as `feat`, `fix`, `perf`, `docs`, `chore`, `ci`, and a `BREAKING CHANGE:` footer. [Semantic Versioning](https://semver.org/) uses `MAJOR.MINOR.PATCH`.

**Why it matters.** The commit log becomes machine-readable: tools derive the next version and the changelog. This project's `scripts/next_version.py` does exactly that:

| Commits since `v1.4.2` | Next version |
|---|---|
| `docs: …`, `chore: …` | `v1.4.2` (no release) |
| `fix: …` | `v1.4.3` |
| `feat: …` (and fixes) | `v1.5.0` |
| `feat!: …` or `BREAKING CHANGE:` footer | `v2.0.0` |

Tags (`git tag -a v1.5.0`) mark releases. Annotated tags carry an author and message and can be signed. Tools such as semantic-release or release-please **[External]** automate tagging and changelogs.

### 3.5 Continuous integration

**What it is.** Every push is built and tested automatically, and the result is reported on the PR.

**Why it matters.** The cost of a bug grows with the time between writing it and finding it. CI shrinks that time to minutes.

**How it works.** Order stages from cheapest and most likely to fail, to slowest:

```text
 lint (s) → typecheck (s) → unit (s) → integration (min) → build
 → scan → publish     (lint/type/test run in parallel; build waits)
```

| Practice | Why |
|---|---|
| Target under 10 minutes for PR feedback | People wait for it; slow CI gets bypassed |
| Cache dependencies (`setup-python` `cache: pip`, Docker layer cache `type=gha`) | Do not re-download the internet on every run |
| Matrix builds (Python 3.12 and 3.13) with `fail-fast: false` | See every broken combination at once |
| Upload JUnit XML as an artifact, `if: always()` | Failures are readable without re-running |
| Pin dependency versions; lock files | Same input, same result |
| Tests own their data (in-memory DB, fakes) | No shared state, no order dependence |

**Flaky test policy.** A test that sometimes fails destroys trust in CI. Policy: a flaky test is a bug. Quarantine it (skip with a ticket and an owner) within a day, fix or delete it within a sprint, and never let "re-run until green" become the norm. Automatic retries are acceptable only when retries are counted and reported.

### 3.6 Continuous delivery and deployment strategies

**What it is.** *Continuous delivery*: every change on `main` is deployable, and deploys are a button. *Continuous deployment*: no button, every green change goes to production.

**Why it matters.** Small, frequent, reversible deploys are less risky than big, rare ones.

**How it works.**

- **Environments.** dev → staging → production, each with its own config, secrets and approvals.
- **Promote the same artifact.** Tag images with the git SHA, and deploy by **digest** (`repo@sha256:…`). A tag can be moved; a digest cannot. Configuration differences come from the environment (env vars, ConfigMaps, secrets), never from a rebuild.
- **Verify, then roll back.** `kubectl rollout status` waits for readiness; a smoke test proves `/health` and that `/version` reports the new SHA; on failure, `kubectl rollout undo` returns to the previous ReplicaSet.

| Strategy | How | Rollback | Cost |
|---|---|---|---|
| Rolling (Kubernetes default) | Replace pods a few at a time (`maxSurge`, `maxUnavailable`) | `rollout undo` (minutes) | Two versions serve at once briefly |
| Blue-green | Full new stack, switch traffic at once | Switch back (seconds) | Double capacity during deploy |
| Canary | Send 1% → 10% → 100% of traffic, watch metrics | Stop and shift back | Needs traffic splitting + metrics (Argo Rollouts, Flagger **[External]**) |
| Feature flags | Deploy code dark, enable per user or percentage | Turn the flag off (no deploy) | Flag debt; must clean up |

**Database migrations in pipelines: expand and contract.** A rolling deploy runs old and new code at the same time, so every migration must work with both:

```text
 1 expand   add new column (nullable) / new table   ← deploy N
 2 migrate  code writes both, backfill old rows     ← deploy N+1
 3 switch   code reads new column only              ← deploy N+2
 4 contract drop old column                         ← deploy N+3
```

Run the migration as its own pipeline step (a Kubernetes Job or `alembic upgrade head` before `set image`), and never put a destructive change in the same deploy as the code that stops using it. Rolling back code is easy; rolling back a dropped column is not.

**Approvals and gates.** A gate is anything that must be true before promotion: tests green, scan clean, staging smoke passed, a human approval, a change ticket. Prefer automated gates; keep human approval for production and make it fast (one click, with evidence linked).

### 3.7 Pipeline security

**What it is.** Treating the pipeline as production infrastructure: it holds credentials that can change production.

**Why it matters.** A compromised CI job can push a malicious image or read every secret. In March 2025 the popular `tj-actions/changed-files` action had its version tags rewritten to malicious code that printed secrets into build logs (CVE-2025-30066) **[External]**. Every repository using `@v45` ran it.

**How it works.**

| Control | In this project |
|---|---|
| **OIDC federation instead of long-lived keys** **[Current]** | `id-token: write` lets the job get a signed GitHub token; AWS STS exchanges it for 1-hour credentials on a role whose trust policy only accepts this repo and branch or environment ([GitHub: OIDC in AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [AWS: OIDC identity providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)) |
| Least privilege `GITHUB_TOKEN` | Top-level `permissions: contents: read`; only jobs that talk to AWS add `id-token: write` |
| Separate roles | `AWS_CI_ROLE_ARN` can push to ECR only; `AWS_DEPLOY_ROLE_ARN` can only update the EKS deployment |
| Pin actions | Major tags here for readability; SHA pinning recommended in production (below) |
| Scan images | Trivy **[External]** fails the build on fixable HIGH/CRITICAL CVEs; Grype **[External]** is an alternative |
| SBOM and provenance | `docker buildx build --sbom=true --provenance=mode=max` or `actions/attest-build-provenance`; SLSA Build levels describe how tamper-resistant the build is ([slsa.dev](https://slsa.dev/spec/v1.0/levels) **[External]**) |
| Dependency updates | Dependabot or Renovate **[External]** for pip, Docker base images and GitHub Actions |
| Untrusted PRs | `pull_request` from forks gets no secrets; avoid `pull_request_target` with a checkout of PR code |

The OIDC trust policy is where the security lives:

```json
"Condition": {
  "StringEquals": {
    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
    "token.actions.githubusercontent.com:sub":
      "repo:acme/pricing-api:environment:production"
  }
}
```

**Pinning by SHA.** `uses: actions/checkout@v5` follows a tag that the action's owner (or an attacker) can move. `uses: actions/checkout@<40-char-sha> # v5.0.0` is immutable. The trade-off is readability and update effort; Dependabot updates SHA pins and keeps the version comment. This project uses major tags so the YAML stays readable in print, and the policy test rejects branch refs like `@main`. In a real repository, pin by SHA and let Dependabot raise the PRs. GitHub also lets organizations require SHA pinning through the allowed-actions policy ([security hardening](https://docs.github.com/en/actions/reference/security/secure-use) **[Provider-specific]**).

### 3.8 GitHub Actions concepts

| Concept | Meaning |
|---|---|
| Workflow | A YAML file in `.github/workflows/`, triggered by events (`on:`) |
| Job | A set of steps on one runner; jobs run in parallel unless `needs:` orders them |
| Step | A shell command (`run:`) or an action (`uses:`) |
| Runner | GitHub-hosted VM (`ubuntu-24.04`) or self-hosted (inside the customer network) |
| `needs` / `outputs` | Ordering and passing values (the image digest) between jobs |
| `environment` | Named target with protection rules: required reviewers, wait timer, allowed branches, environment secrets ([docs](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)) |
| `concurrency` | At most one run per group; `cancel-in-progress` for PRs, queue for deploys |
| `permissions` | Scopes of the automatic `GITHUB_TOKEN`; set the default to read |
| Reusable workflow | `on: workflow_call`; called with `uses: org/repo/.github/workflows/deploy.yml@ref`; one deploy definition for many services |
| `vars` / `secrets` | Non-secret config vs encrypted values; both per repo, org or environment |

Note: required reviewers and wait timers on environments in **private** repositories need GitHub Enterprise; public repositories get them on every plan **[Provider-specific]**.

### 3.9 Jenkins

**What it is.** A self-hosted automation server **[External]**, still the most common CI system inside large enterprises and air-gapped networks. A *declarative pipeline* in a `Jenkinsfile` is the current style; freestyle jobs and scripted pipelines are **[Legacy]** for new work ([Pipeline syntax](https://www.jenkins.io/doc/book/pipeline/syntax/)).

| Directive | Meaning | GHA equivalent |
|---|---|---|
| `agent` | Where to run: `label`, `docker`, `kubernetes` (pod template) | `runs-on`, `container:` |
| `stages` / `stage` / `steps` | Ordered phases | jobs + steps |
| `when { branch 'main' }` | Conditional stage | `if:` |
| `post { always / failure / cleanup }` | Hooks after a stage or the pipeline | `if: always()` / `failure()` |
| `input { submitter … }` | Pause for human approval | environment required reviewers |
| `withCredentials([...])` | Bind a stored credential to an env var for a block, masked in logs | `secrets.X` |
| `options { disableConcurrentBuilds() }` | One build per branch | `concurrency` |
| Shared library `@Library('x') _` | Reusable Groovy steps (`deploy()`) across repos | reusable workflows |
| Multibranch pipeline | One job per branch/PR discovered from the repo | the default in GHA |

Practical notes: run builds on ephemeral agents (Kubernetes pods), never on the controller; get AWS access from the agent's IAM role (instance profile, IRSA or EKS Pod Identity) rather than stored keys; an `input` step inside a stage that holds an agent keeps an executor busy while waiting, so production approval often uses `agent none` for that stage.

### 3.10 Comparing CI/CD systems

| | GitHub Actions | Jenkins | GitLab CI | Azure DevOps Pipelines |
|---|---|---|---|---|
| Definition | `.github/workflows/*.yml` | `Jenkinsfile` (Groovy DSL) | `.gitlab-ci.yml` | `azure-pipelines.yml` |
| Hosting | SaaS + self-hosted runners | Self-hosted only | SaaS or self-managed | SaaS or Server |
| Reuse | Actions, reusable workflows | Shared libraries, plugins | `include:`, components | Templates, task extensions |
| Approvals | Environment reviewers | `input` step | Protected environments, manual jobs | Environment approvals and checks |
| Cloud auth | OIDC `id-token` | Agent IAM role, plugins | `id_tokens:` (OIDC) | Workload identity federation |
| Strength | Tight GitHub integration, marketplace | Flexibility, air-gapped, plugins | All-in-one DevOps platform | Microsoft and Azure shops |
| Weakness | Tied to GitHub; marketplace supply chain | Plugin upkeep, controller ops, Groovy | Tied to GitLab | Verbose YAML |

The concepts transfer: stages, artifacts, environments, approvals, secrets, OIDC. Learn one deeply and map the others.

### 3.11 Testing the pipeline itself

Pipeline YAML is code that can delete production. Treat it that way:

- **Lint:** `actionlint` **[External]** catches bad expressions, unknown inputs and shell issues in workflows; Jenkins has a declarative linter (`jenkins-cli declarative-linter`).
- **Run locally:** `act` **[External]** runs GitHub Actions jobs in Docker. It is approximate (no OIDC, different images), so use it for fast iteration, not as proof.
- **Policy tests:** parse the YAML and assert rules: read-only default permissions, deploys depend on tests, production has an environment, no access keys. This project has 20 such tests. Larger organizations use OPA/Conftest **[External]** for the same idea.

One gotcha teaches YAML itself: **PyYAML implements YAML 1.1, where the bare key `on` means boolean `True`** (as do `yes`, `no`, `off`). GitHub reads it as the string `"on"`. So in Python the triggers are under `workflow[True]`:

```python
>>> yaml.safe_load("on: push")
{True: 'push'}
```

## 4. Application in a Real System

A customer's team ships a pricing service by SSH-ing to a server and running `git pull`. Deploys happen on Friday nights; nobody knows which commit is live. The FDE introduces the pipeline in this unit in a week:

- **Day 1:** protect `main`, add CODEOWNERS for `/.github/`, and make lint and tests required checks. Agree on squash merges with conventional-commit PR titles.
- **Day 2:** containerize, add `/version` with the git SHA, push images to ECR using an OIDC role. Delete the old IAM user's access keys.
- **Day 3:** staging deploy with smoke test and automatic rollback. Demonstrate it by deploying a commit that breaks `/health`, and show the pipeline rolling back on its own.
- **Day 4:** production environment with two required reviewers from the customer's team. Their change process now links to a pipeline run with test report, scan result and the image digest.
- **Day 5:** pipeline policy tests, Dependabot for actions and base images, and a one-page runbook ("how to hotfix, how to roll back").

Alternatives the FDE weighs: if the customer already runs Jenkins inside a closed network, use the Jenkinsfile with the same stages instead of introducing a new tool. If they want GitOps, the pipeline's last step becomes "commit the new digest to the deploy repo" and Argo CD **[External]** applies it.

## 5. Implementation

### 5.1 `/version`: the proof a deploy landed

```python
@app.get("/version", tags=["ops"])
async def version() -> dict[str, str]:
    return {
        "version": settings.version,
        "git_sha": settings.git_sha,
        "env": settings.env,
    }
```

The Dockerfile turns build arguments into those settings, so the image carries its own identity:

```dockerfile
ARG GIT_SHA=unknown
ARG APP_VERSION=0.0.0-dev
ENV APP_GIT_SHA=${GIT_SHA} \
    APP_VERSION=${APP_VERSION}
```

### 5.2 The smoke test's retry loop

During a rolling update, some pods still serve the old SHA for a few seconds. A single probe would fail randomly, so the script retries both failure kinds and only reports the last one:

```python
for attempt in range(1, config.attempts + 1):
    try:
        served = probe_once(client, config.expected_sha)
    except SmokeFailure as failure:
        last = failure
        log(f"attempt {attempt}/{config.attempts}: {failure}")
        if attempt < config.attempts:
            sleep(config.delay_seconds)
        continue
    log(f"smoke test passed: serving {served}")
    return EXIT_OK
return last.exit_code   # 1 = unhealthy, 3 = wrong version
```

`sleep` and `log` are parameters, so tests run instantly with `httpx.MockTransport`. Distinct exit codes let an operator tell "the service is down" from "the old version is still serving" at a glance.

### 5.3 Least privilege and concurrency at the top of the workflow

```yaml
permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

New pushes to a PR cancel the stale run. Runs on `main` queue instead, because killing a deploy halfway leaves a cluster in an unknown state.

### 5.4 Build once: OIDC, scan, push, record the digest

```yaml
build:
  needs: [lint, typecheck, test]
  permissions:
    contents: read
    id-token: write # OIDC: short-lived AWS credentials, no keys
  outputs:
    image: ${{ steps.push.outputs.image }}
  steps:
    # … build with load: true, then Trivy scan, then:
    - name: Configure AWS credentials (OIDC)
      if: env.IS_MAIN == 'true'
      uses: aws-actions/configure-aws-credentials@v5
      with:
        role-to-assume: ${{ vars.AWS_CI_ROLE_ARN }}
        aws-region: ${{ vars.AWS_REGION }}
    - name: Push and record the immutable digest
      id: push
      run: |
        docker push "$IMAGE"
        digest=$(docker inspect \
          --format '{{index .RepoDigests 0}}' "$IMAGE")
        echo "image=$digest" >> "$GITHUB_OUTPUT"
```

The image is scanned *before* it is pushed, so a vulnerable image never reaches the registry. PRs build and scan too, but never authenticate to AWS.

### 5.5 Deploy, verify, roll back

```yaml
- name: Roll out the image digest
  run: |
    kubectl -n "$NAMESPACE" set image \
      deployment/pricing-api app="$IMAGE"
    kubectl -n "$NAMESPACE" rollout status \
      deployment/pricing-api --timeout=180s
- name: Smoke test
  run: >-
    python -m scripts.smoke_test
    --base-url "${{ vars.STAGING_URL }}"
    --expected-sha "$GITHUB_SHA"
- name: Roll back on failure
  if: failure()
  run: |
    kubectl -n "$NAMESPACE" rollout undo deployment/pricing-api
```

`deploy-production` has the same steps, `needs: [build, deploy-staging]`, `environment: production` (required reviewers configured in repository settings), and the same `IMAGE: ${{ needs.build.outputs.image }}`. Promotion, not rebuild.

### 5.6 The Jenkins equivalent

```groovy
stage('Approve Production') {
  when { branch 'main' }
  options { timeout(time: 4, unit: 'HOURS') }
  input {
    message 'Promote this build to production?'
    ok 'Deploy'
    submitter 'release-managers'   // Jenkins group allowed
  }
  steps { echo "Approved ${env.GIT_COMMIT} for production" }
}
// …
post {
  failure {
    script {
      if (env.DEPLOYED_TO) { rollback(env.DEPLOYED_TO) }
    }
  }
}
```

### 5.7 A policy test, including the YAML gotcha

```python
def triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # YAML 1.1 (PyYAML) reads the bare key `on` as True.
    value = workflow.get("on", workflow.get(True))
    ...

def test_build_and_deploys_depend_on_all_checks(jobs) -> None:
    for name in ("build", *DEPLOY_JOBS):
        upstream = all_upstream(name, jobs)   # transitive `needs`
        assert {"lint", "typecheck", "test"} <= upstream, name
```

If someone "temporarily" removes `needs: [build]` from a deploy job, this test fails on the PR that does it.

## 6. How It Connects to the Rest of the System

```text
 Unit 7 pipeline
   ├─ runs the tests written in U1-U5 (pytest, contract, e2e)
   ├─ builds the image and deploys the manifests from U6
   │    (probes, rollout, ECR, EKS, IAM roles)
   ├─ will deploy the services of U8; contract tests guard their APIs
   ├─ U9-U10: prompt/eval suites become a CI gate for AI features
   ├─ U11: deploy markers on dashboards; canary analysis uses metrics
   └─ U12: the pipeline run is the FDE's evidence for change boards
```

## FDE Scenario 6 — "Our change board needs approvals, and our Jenkins can't reach the internet"

**Stakeholder (customer's head of IT operations):** "We like your pipeline, but you'll be deploying from our Jenkins. It has no internet access. Every production change needs CAB approval with evidence. And by the way, we have a pricing bug that has to go out today."

- *Clarify first:* What can the network reach (internal Git, an artifact mirror such as Artifactory or Nexus, an internal registry, ECR through a VPC endpoint)? What evidence does the CAB want? Is there a "standard change" category for pre-approved, low-risk deploys? Who can approve today?
- *Make the pipeline work offline:*
  - Python packages from the internal mirror (`PIP_INDEX_URL` as a Jenkins global property), with pinned versions and hashes;
  - base images mirrored into the internal registry or ECR (pull-through cache), referenced by digest;
  - scanner databases (Trivy's vulnerability DB) mirrored on a schedule;
  - no `curl | sh` steps and no marketplace downloads at build time.
- *Map the CAB to pipeline gates:* the Jenkins `input` step is the approval, restricted to the CAB group with `submitter`. The approval message links the evidence: commit and PR, JUnit report, scan result, image digest, staging smoke result, rollback plan. Propose that pipeline deploys with all gates green qualify as a standard change; that is how teams keep auditability without weekly waits.
- *The hotfix today:* do not bypass the pipeline. Branch from the commit currently in production (from `/version`), apply the minimal `fix:` commit with a regression test, run the full pipeline, and ask for an emergency CAB approval with the same evidence. Merge or cherry-pick the fix to `main` so the next release does not reintroduce the bug.
- *What must be deterministic:* the artifact (one digest from staging to production), the approval record, and rollback (`rollout undo`, tested in staging).
- *Communicate:* a short note to the CAB: what changes, the risk, how it was tested, how to roll back, who is on call. Facts, not reassurance.

## Comprehension Questions

1. Why does trunk-based development usually beat GitFlow for a web service?
2. When do you use `git revert` and when `git reset`?
3. Why do you promote an image *digest* instead of rebuilding or retagging per environment?
4. What does the `id-token: write` permission do, and why is it better than storing AWS access keys as secrets?
5. Why does the smoke test retry on a SHA mismatch instead of failing immediately?
6. Why do PR runs cancel in progress but `main` runs do not?
7. What is expand-and-contract, and why does a rolling deploy require it?
8. Why does PyYAML return `True` as a key when parsing a GitHub workflow?

## Comprehension Answers

1. Short-lived branches mean small merges, fast feedback and a `main` that always reflects what will ship. GitFlow's long-lived branches create big, risky merges and make "what is in production" unclear. GitFlow still fits products with several supported releases.
2. `revert` adds a new commit that undoes an old one; use it for anything already pushed or shared. `reset` moves a branch pointer and discards commits; use it only on local, unpublished work.
3. A digest identifies the exact bytes that were tested. Rebuilding can pull different dependencies or base layers; tags can be moved. Promoting the digest guarantees production runs what staging verified.
4. It lets the job request a short-lived, signed OIDC token from GitHub, which AWS STS exchanges for temporary credentials on a role whose trust policy restricts repo, branch or environment. Nothing long-lived can leak, and nothing needs rotation.
5. During a rolling update, old and new pods serve traffic side by side for a short time. A mismatch is only a real failure if it persists after the rollout should have finished.
6. A new push to a PR makes the old run useless, so cancelling saves time. On `main`, a run may be mid-deploy; cancelling it can leave the cluster half updated, so runs queue.
7. Change the schema in backward-compatible steps: add, migrate and dual-write, switch reads, then remove. During a rolling deploy, old and new code run at the same time against the same database, so every schema state must work with both.
8. PyYAML implements YAML 1.1, where `on`, `off`, `yes` and `no` are booleans. GitHub's parser treats `on` as a string. Tests must read `workflow.get("on", workflow.get(True))`.

## Interview Questions — Theory-Based

**Q1. Design a CI/CD pipeline for a containerized Python service.**

- *Strong answer:* PR: lint, typecheck, unit tests in parallel (matrix, cached deps, JUnit artifacts), then integration tests; build the image, scan it. Main: same checks, push the image tagged with the SHA to the registry using OIDC, deploy the digest to staging, wait for rollout, smoke test, roll back on failure; production behind an environment approval, same digest, smoke test, rollback. Mention concurrency, least-privilege permissions, and where migrations run.
- *What it tests:* end-to-end delivery thinking, not tool trivia.
- *Follow-up:* "How do you make it faster?" (Parallel jobs, caching, test splitting, running only affected tests in a monorepo, smaller images.)

**Q2. How do you authenticate a pipeline to AWS?**

- *Strong answer:* OIDC federation: GitHub (or GitLab) issues a signed token per job; an IAM role trusts the provider with conditions on `aud` and `sub` (repo, branch, environment); STS returns short-lived credentials. Separate roles for push and deploy. For Jenkins on AWS, use the agent's IAM role (IRSA / Pod Identity). Long-lived access keys are the last resort.
- *Follow-up:* "What goes wrong with a too-broad `sub` condition?" (`repo:acme/*` lets any repo, or any branch, assume the production role.)

**Q3. Compare rolling, blue-green and canary deployments.**

- *Strong answer:* use the table in §3.6. Add that rollback speed, capacity cost and the need for traffic splitting and good metrics drive the choice; feature flags separate deploy from release.

**Q4. What is a flaky test and what do you do about one?**

- *Strong answer:* a test that passes and fails on the same code. Causes: timing, shared state, order dependence, real network, time zones. Quarantine with an owner, fix the cause, track flake rate; do not normalize retries.

**Q5. Why pin GitHub Actions by SHA?**

- *Strong answer:* tags are mutable; a compromised maintainer account or a moved tag runs new code with your secrets (the 2025 `tj-actions/changed-files` incident). SHA pins are immutable; Dependabot keeps them current; add least-privilege permissions so a bad action can do less.

**Q6. How do you handle database migrations in continuous deployment?**

- *Strong answer:* expand and contract; migrations as a separate, idempotent pipeline step before the code that needs them; never a destructive change in the same release as the code change; test migrations against a production-like copy; roll forward when rollback would lose data.

**Q7. GitHub Actions or Jenkins?**

- *Strong answer:* depends on context. Actions for GitHub-hosted code, SaaS runners, fast setup and OIDC out of the box. Jenkins when the customer already runs it, needs air-gapped or highly custom builds, or has many shared libraries. The pipeline design (stages, gates, artifacts, rollback) is the same in both.

**Q8. What is the difference between continuous delivery and continuous deployment?**

- *Strong answer:* delivery: every change is releasable and deploys are push-button, often with an approval. Deployment: every green change goes to production automatically. Regulated customers usually want delivery with automated evidence.

## Interview Questions — Application / Experience-Based

**A1. Tell me about a pipeline you built or improved.**

- *Cover:* starting state, the goals (speed, safety, audit), the stages you added, how secrets were handled, the result in numbers.
- *Structure:* situation → requirement → pipeline design → implementation → verification → result → lesson.
- *Personalize:* "`<<personalize: team/system>>` deployed `<<how, how often>>`. I built `<<CI tool>>` stages for `<<checks>>`, deployed to `<<target>>` with `<<strategy>>`. Lead time went from `<<before>>` to `<<after>>`."
- *Lab-honest version:* "In a project I built a GitHub Actions pipeline for a FastAPI service: lint, mypy and a pytest matrix with JUnit reports; image build and Trivy scan; push to ECR with OIDC; staging deploy to EKS with a smoke test that checks the deployed git SHA and rolls back automatically; production behind an environment approval. I wrote the Jenkins equivalent and 20 policy tests for the pipeline itself."
- *Follow-ups:* "How long did the pipeline take?" "What failed most often?"

**A2. Describe a time a deploy went wrong.**

- *Cover:* detection (alert, smoke test, user report), the decision to roll back or roll forward, communication, root cause, the pipeline change that prevents a repeat.
- *Personalize:* `<<personalize: incident, detection, rollback time, prevention>>`.
- *Lab-honest version:* "I haven't caused a production incident through a deploy. In my lab pipeline I tested the failure path on purpose: I deployed an image whose `/version` reported the wrong SHA, watched the smoke test exit with code 3 and the rollback step restore the previous ReplicaSet."
- *Follow-ups:* "When would you roll forward instead?"

**A3. How have you handled secrets in CI/CD?**

- *Cover:* where secrets live (secret manager, CI secret store), OIDC instead of static keys, masking, rotation, least privilege, keeping secrets out of fork PRs and logs.
- *Personalize:* `<<personalize: tools, one specific improvement>>`.
- *Lab-honest version:* describe the OIDC role setup and the policy test that rejects access-key patterns.

**A4. Tell me about adapting to a customer's existing tooling or process.**

- *Cover:* listening first, mapping their process (CAB, Jenkins, air gap) to the pipeline, the compromise you proposed, the evidence that it worked.
- *Personalize:* `<<personalize: customer constraint, your adaptation, outcome>>`.
- *Lab-honest version:* walk through FDE Scenario 6 as "how I would approach it."

**A5. How do you keep `main` green on a busy team?**

- *Cover:* required checks, merge queue, fast CI, small PRs, revert-first culture when `main` breaks, flaky-test policy, ownership of the build.
- *Personalize:* `<<personalize: team size, a practice you introduced>>`.

## Troubleshooting Scenarios

**T1. `configure-aws-credentials` fails: "Not authorized to perform sts:AssumeRoleWithWebIdentity".**

```text
SYMPTOM     OIDC step fails on main; worked yesterday or never worked
CHECK       job has permissions: id-token: write?
            IAM OIDC provider exists for token.actions.githubusercontent
            trust policy aud = sts.amazonaws.com
            trust policy sub matches: repo:ORG/REPO:ref:refs/heads/main
            or repo:ORG/REPO:environment:production (env jobs!)
CAUSES      job uses `environment:` so sub is environment-based, but
            policy expects a ref; repo renamed; permission missing
CONFIRM     print claims: decode the token in a debug job (no secrets)
FIX         match sub to how the job runs; add id-token: write
PREVENTION  policy test for id-token; document trust policy in repo
```

**T2. The deploy job succeeds but users still see the old behavior.**

```text
SYMPTOM     pipeline green, bug still present
CHECK       curl /version: which git_sha is serving?
            kubectl get deploy -o jsonpath='{..image}'
            image tag reused (":latest")? imagePullPolicy IfNotPresent?
            CDN/browser cache for frontend assets?
CAUSES      mutable tag, node cached old image; set image to same tag
            so no rollout happened; smoke test not checking the sha
FIX         deploy by digest; immutable ECR tags; smoke test the sha
PREVENTION  /version check in every deploy (this project's exit 3)
```

**T3. Tests pass locally but fail in CI.**

```text
SYMPTOM     green on laptop, red in CI (or only on one matrix entry)
CHECK       Python version; dependency versions (lock file?); env vars
            present locally only (.env); time zone/locale; test order
            (pytest -p randomly); file paths and case sensitivity
CAUSES      unpinned deps; hidden reliance on local state; 3.12 vs
            3.13 behavior difference; network in tests
CONFIRM     reproduce in the same container image as CI
FIX         pin and lock; fakes instead of network; explicit settings
PREVENTION  matrix build; tests own their data; no .env in tests
```

**T4. `kubectl rollout status` times out in staging.**

```text
SYMPTOM     rollout status exceeds --timeout, then rollback runs
CHECK       kubectl describe pod: ImagePullBackOff? CrashLoopBackOff?
            readiness probe failing? kubectl logs --previous
            node capacity (Pending pods)? missing secret/config?
CAUSES      node role cannot pull from ECR; app crashes on new
            required setting; probe path changed; resource limits
FIX         fix IAM/pull secret; add the config; correct probe
PREVENTION  start the container in CI (docker run + curl /health);
            config validated at startup so failures are immediate
```

**T5. Every PR run spends 6 minutes installing dependencies.**

```text
SYMPTOM     slow CI, mostly in pip install / docker build
CHECK       setup-python cache hit? cache key includes the right
            requirements file? Docker layers ordered for caching
            (COPY requirements before COPY app)? cache-from gha?
CAUSES      cache-dependency-path wrong; app copied before deps;
            cache scope evicted (10 GB repo limit)
FIX         correct cache paths; reorder Dockerfile; cache-to mode=max
PREVENTION  watch pipeline duration as a metric; budget < 10 min
```

**T6. Jenkins: a credential appears in the console log.**

```text
SYMPTOM     secret visible in build output
CHECK       used outside withCredentials? echoed via set -x? passed
            through Groovy string interpolation ("${SECRET}") instead
            of the shell ('$SECRET')? transformed (base64) so masking
            misses it?
FIX         rotate the secret now; single-quoted sh with env vars;
            keep secrets inside withCredentials blocks
PREVENTION  code review on Jenkinsfile; prefer IAM roles over secrets
```

## Unit Practice Project — Pipeline for a FastAPI Service

### Project Goal

Build a complete, testable delivery pipeline for a small FastAPI service:

- the service reports its build identity (`/version` with git SHA);
- a smoke-test script proves a deploy landed and drives rollback;
- a version helper derives semver from conventional commits;
- a GitHub Actions workflow and an equivalent Jenkinsfile run checks, build, scan, push, staged deploy, approval and rollback;
- policy tests keep the pipeline definition safe as people edit it.

### Architecture

```text
 app/ (FastAPI)          scripts/                 pipeline definitions
  /health                 smoke_test.py ◄──────── deploy jobs / stages
  /version (sha, ver)       retries, exit 0/1/3
  /quote → pricing.py     next_version.py ◄────── build job (version)
                            conventional → semver
 Dockerfile: ARG GIT_SHA → ENV APP_GIT_SHA, non-root
 .github/workflows/ci.yml   Jenkinsfile
        ▲                        ▲
        └──── tests/test_pipeline_policy.py (pyyaml + regex)
```

### Requirements

1. `GET /health` returns `{"status":"ok"}`; `GET /version` returns `version`, `git_sha`, `env` from `APP_*` settings.
2. `GET /quote?unit_price=&quantity=` returns a volume-discounted total as a string with two decimals (Decimal, half-up rounding).
3. `scripts/smoke_test.py` checks `/health` and that `/version` matches `--expected-sha` (short or full), retrying with a delay and per-request timeout; exit 0 pass, 1 unhealthy, 2 bad arguments, 3 wrong version.
4. `scripts/next_version.py` computes the next version from NUL-separated commit messages.
5. The workflow runs on `pull_request` and `push` to `main`, with read-only default permissions and a concurrency group.
6. Lint, typecheck and a 3.12/3.13 test matrix with uploaded JUnit reports run in parallel; build waits for all three.
7. Build tags the image with the git SHA, scans it, and pushes to ECR only on `main`, using OIDC.
8. Staging deploys the built digest, runs the smoke test and rolls back on failure.
9. Production needs staging, uses `environment: production`, and deploys the same digest.
10. The Jenkinsfile has the same stages in order, a JUnit report, an `input` approval and a rollback in `post { failure }`.
11. Policy tests enforce rules 5–10 and reject plaintext AWS keys.

### Technical Requirements

- Python 3.12+, FastAPI, pydantic-settings, httpx, PyYAML; pytest, ruff, mypy (strict).
- GitHub Actions (`ubuntu-24.04` runners), AWS ECR and EKS, `aws-actions/configure-aws-credentials` with OIDC.
- Jenkins with the Pipeline, Docker Pipeline and Credentials Binding plugins.
- No runner or cluster needed to verify: everything is checked by pytest.

### Project Structure

{{tree projects/unit07-cicd/solution}}

### Step-by-Step Implementation

1. **Run the starter.** `pytest -q` shows 25 passed, 38 failed. Start the service and `curl /version`.
   - *Why:* the failing tests are your specification.
2. **TODO 3–4: `next_version.py`.** Classify a commit, then apply the bump.
   - *Test:* `pytest -q tests/test_next_version.py`.
3. **TODO 1–2: `smoke_test.py`.** SHA comparison, then the retry loop.
   - *Test:* `pytest -q tests/test_smoke_test.py`; then run it against your local server with `--expected-sha local`.
4. **TODO 5–6: workflow security and ordering.** Top-level permissions and concurrency; `needs` and the OIDC permission on `build`.
   - *Test:* `pytest -q tests/test_pipeline_policy.py -k "permissions or concurrency or oidc"`.
5. **TODO 7–8: deploy jobs.** Staging with smoke test and rollback; production with environment and the same image.
   - *Test:* `pytest -q tests/test_pipeline_policy.py`.
   - *Optional:* run `actionlint` if you have it installed.
6. **TODO 9: Jenkinsfile.** Add the four deploy-side stages and the rollback.
   - *Test:* `pytest -q -k jenkins`.
7. **TODO 10: write two policy tests.** Make them fail first by breaking the workflow on purpose, then restore it.
8. **Finish:** `ruff check . && ruff format --check . && mypy && pytest -q`.

### Starter Code

{{file projects/unit07-cicd/starter/scripts/smoke_test.py}}

{{file projects/unit07-cicd/starter/.github/workflows/ci.yml}}

The starter also has TODOs in `scripts/next_version.py` (classify and bump), `Jenkinsfile` (deploy, smoke, approval stages and rollback) and `tests/test_pipeline_policy.py` (two policy tests to write). The task table is in the starter `README.md`.

### Practice Tasks

1. **Normal behavior:** run the service, call `/version` and `/quote`, run the smoke test against it with the right and wrong SHA, and check the exit codes with `echo $?`.
2. **Validation:** `--attempts 0`, a missing `--base-url`, `next_version` with `1.4` as the current version.
3. **Failure paths:** stop the server mid-run (exit 1); point the smoke test at a page that returns HTML (exit 1); serve a different `APP_GIT_SHA` (exit 3).
4. **Security edge cases:** add `id-token: write` to the `lint` job and watch the policy test fail; paste a fake `AKIA…` string into a comment; change an action to `@main`.
5. **Extend:**
   - add a `migrate` job between build and staging that runs `alembic upgrade head` as a Kubernetes Job;
   - turn the deploy steps into a reusable workflow (`on: workflow_call`) and call it twice;
   - add `.github/dependabot.yml` for `pip`, `docker` and `github-actions`;
   - add a tag-and-release job that pushes `vX.Y.Z` from `next_version` (needs `contents: write` on that job only).

### Hints

1. For short SHAs, accept the match if either string starts with the other, and treat an empty served SHA as a mismatch.
2. In the retry loop, sleep only *between* attempts: `attempts - 1` sleeps in total. The tests count them.
3. `IntEnum` makes `max()` across commits pick the biggest bump.
4. A job-level `permissions:` block replaces the top-level one entirely, so repeat `contents: read` next to `id-token: write`.
5. Remember the YAML gotcha: in Python, `workflow["on"]` raises `KeyError`; the triggers are under `True`.
6. In the Jenkinsfile, set `env.DEPLOYED_TO` *before* calling `deploy()`, so a failed rollout still triggers the rollback.

### Expected Behavior

```text
GET /version  → {"version":"1.4.0","git_sha":"abc1234def","env":"test"}
GET /quote?unit_price=19.99&quantity=12   → {"total":"227.89",...}
smoke_test --expected-sha <served sha>    → "smoke test passed", 0
smoke_test --expected-sha deadbee         → 10 attempts, then 3
smoke_test, server down                   → 10 attempts, then 1
smoke_test --attempts 0                   → usage error, 2
printf 'fix: a\0feat: b\0' | next_version v1.4.2   → v1.5.0
printf 'feat!: drop v1\0'  | next_version 1.4.2    → 2.0.0
pytest -q tests/test_pipeline_policy.py            → 20 passed
```

### Testing Requirements

- **App (5):** health, version metadata, `APP_*` settings, quote with discount, quote validation.
- **Pricing (10):** tier boundaries, rounding, custom tiers, invalid inputs.
- **Smoke test (9):** pass, short SHA, wrong SHA after retries, unhealthy, recovery during rollout, connection errors, non-JSON body, CLI end to end, bad arguments.
- **Next version (19):** classification table, bumps, invalid version, largest bump wins, CLI with NUL-separated input.
- **Pipeline policy (20):** the `on` gotcha, triggers, permissions, concurrency, OIDC scope, no write on contents, transitive `needs`, environments, main-only deploys, digest promotion, smoke and rollback, matrix and reports, pinned actions, no AWS keys, timeouts, Jenkins stage order, approval and rollback, Jenkins `when`, Dockerfile non-root and SHA, 76-column limit.

```bash
ruff check . && ruff format --check . && mypy && pytest -q
```

### Final Runnable Solution

{{files projects/unit07-cicd/solution}}

### How to Run

```bash
cd projects/unit07-cicd/solution
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env
APP_GIT_SHA=$(git rev-parse --short HEAD) \
  uvicorn app.main:create_app --factory --reload

# second terminal
python -m scripts.smoke_test --base-url http://127.0.0.1:8000 \
  --expected-sha "$(git rev-parse --short HEAD)" --attempts 3

# optional, with the tools installed
actionlint .github/workflows/ci.yml
act pull_request -j test          # runs the test job in Docker
```

To use the workflow for real: push the folder as a repository, create the IAM OIDC provider and the two roles, set the variables listed in the README, and create `staging` and `production` environments (production with required reviewers and `main` as the only deployment branch).

### Verify the Solution

1. `pytest -q`: **63 passed** (5 app, 10 pricing, 9 smoke, 19 version, 20 policy).
2. `ruff check .`, `ruff format --check .` and `mypy` (strict, 7 source files) are clean.
3. The starter shows **25 passed, 38 failed** before any TODO is done.
4. Manual: the smoke test against your local server exits 0 with the right SHA and 3 with a wrong one.
5. Break a rule on purpose (remove `needs: [build]` from `deploy-production`) and confirm a policy test fails.

### Project Interview Debrief

1. **Why does the smoke test check the git SHA and not just `/health`?**
   A healthy old version also returns 200. Only the SHA proves the new code is serving. Mismatches are common: a reused tag, a failed rollout that left old pods, or the wrong cluster context.
2. **Why push only after the scan, and only on `main`?**
   A vulnerable image never reaches the registry, and PRs, including PRs from forks, never get AWS credentials. Every image in ECR came from reviewed code that passed every gate.
3. **What stops someone from deploying to production without approval?**
   The production environment's required reviewers and branch rule (enforced by GitHub, not by the YAML), the OIDC trust policy that only accepts `environment:production` for the deploy role, CODEOWNERS on `/.github/`, and the policy tests.
4. **Why is the rollback automatic but the production promotion manual?**
   Rolling back to a known-good version is low-risk and time-critical. Promotion is a business decision that the customer's process may require. Both are recorded in the pipeline run.
5. **How would you move this to the customer's Jenkins?**
   The Jenkinsfile has the same stages. AWS access comes from the agent's IAM role, kubeconfigs from Jenkins credentials, the approval from `input` with a `submitter` group, the rollback from `post { failure }`. Shared logic moves into a shared library, and dependencies come from internal mirrors if the network is closed.
