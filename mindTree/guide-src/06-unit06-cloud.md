# Unit 6 — Cloud-Native Deployment: Docker, Kubernetes and AWS

## 1. What This Unit Teaches

Code that only runs on your laptop is not delivered. An FDE packages the service, deploys it into the customer's cloud account (often into *their* cluster, *their* VPC, under *their* security rules), and keeps it healthy **[JD-Required: Docker, Kubernetes, cloud (AWS/Azure/GCP), deploying and operating services]**. This unit uses AWS as the concrete cloud and maps every service to Azure and GCP. It teaches:

- containers vs virtual machines, images, layers and build caching;
- production Dockerfiles: multi-stage builds, slim bases, non-root users, exec-form commands, `.dockerignore`, tags vs digests;
- Docker Compose for a local stack that mirrors production;
- 12-factor configuration and secrets;
- the Kubernetes objects you must know cold: Pod, Deployment, Service, Ingress / Gateway API, ConfigMap, Secret, probes, resources, HPA, PodDisruptionBudget, RBAC and ServiceAccounts;
- health-endpoint semantics and graceful shutdown (SIGTERM, `preStop`, grace periods);
- AWS building blocks: ECR, EKS vs ECS/Fargate vs Lambda, ALB, RDS, ElastiCache, Secrets Manager, VPC design, security groups, IAM least privilege, IRSA / EKS Pod Identity, CloudWatch;
- infrastructure as code and **policy as code** (testing manifests before they ship).

## 2. Mental Model

```text
 git commit ──► docker build (multi-stage) ──► image :1.0.0 @sha256:…
                                                   │ docker push
                                                   ▼
                                           ECR (private registry)
                                                   │ pull (node IAM)
 ┌──────────────────────── AWS VPC ───────────────┼────────────────────┐
 │ public subnets           private subnets       ▼                    │
 │  ┌─────────┐   HTTPS   ┌──────────────── EKS cluster ────────────┐  │
 │  │   ALB   │──────────►│ Ingress → Service (ClusterIP :80)       │  │
 │  │ (TLS)   │  target:  │   ├─ Pod inventory-api :8000  ready ✔   │  │
 │  └─────────┘  pod IPs  │   ├─ Pod inventory-api :8000  ready ✔   │  │
 │      ▲                 │   └─ Pod (new, rolling)       ready ✘   │  │
 │  internet              │ ConfigMap  Secret  HPA  PDB  SA(IRSA)   │  │
 │                        └──────────────┬───────────────┬──────────┘  │
 │                                       ▼               ▼             │
 │                            RDS Postgres (SG)   Secrets Manager      │
 └─────────────────────────────────────────────────────────────────────┘
   kubelet: startupProbe → livenessProbe (/health/live, restart)
                         → readinessProbe (/health/ready, traffic)
   logs: stdout JSON → CloudWatch / any log backend
```

Three ideas carry the whole unit:

1. **Immutable artifact, configurable environment.** Build one image, tag it with a version and a digest, and promote the *same* image from dev to prod. Only the configuration changes.
2. **The platform needs honest signals.** Kubernetes restarts what fails liveness, routes only to what passes readiness, and kills what exceeds its memory limit. Wrong signals turn a small problem into an outage.
3. **Least privilege everywhere.** Non-root containers, read-only filesystems, private subnets, narrow security groups, one IAM role per workload. Customers' security teams will check every one of these.

## 3. Brief Theory

### 3.1 Containers vs virtual machines

**What it is.** A VM virtualizes hardware and runs a full guest OS kernel. A container is an ordinary Linux process isolated with **namespaces** (what it can see: PIDs, network, mounts, users) and limited with **cgroups** (what it can use: CPU, memory). All containers on a host share its kernel.

**Why it exists.** VMs take minutes to boot and gigabytes per instance. Containers start in milliseconds and package the app *with its dependencies*, so "works on my machine" becomes "works in this image".

**Why it matters.** It explains real behavior: a container is killed by the kernel's OOM killer when it exceeds its cgroup memory limit; PID 1 inside a container must handle signals; a kernel exploit can cross containers but not VMs (that is why multi-tenant platforms like Fargate and Lambda use micro-VMs such as Firecracker).

| | Virtual machine | Container |
|---|---|---|
| Isolation | Hardware (hypervisor) | Kernel namespaces + cgroups |
| Boot time | Tens of seconds to minutes | Milliseconds to seconds |
| Size | GBs (full OS) | MBs (app + userland libs) |
| Kernel | Own | Shared with host |
| Typical use | Strong isolation, other OSes | Packaging and running services |

### 3.2 Images, layers and build caching

**What it is.** An image is a stack of read-only, content-addressed layers plus metadata (entrypoint, env, user). Each Dockerfile instruction that changes the filesystem (`RUN`, `COPY`, `ADD`) creates a layer. A running container adds one thin writable layer on top.

**Why it matters.** Build speed and image size are mostly about layer order. BuildKit (the default builder **[Current]**) reuses a cached layer only if the instruction *and all layers before it* are unchanged.

**How it works.**

```text
 COPY requirements.txt .        ← changes rarely   (cached)
 RUN pip install -r …           ← slow, cached while requirements same
 COPY app ./app                 ← changes every commit (rebuilt, fast)
```

Copy the dependency manifest first, install, then copy the code. Reverse the order and every code change reinstalls every dependency. Docs: [Docker build cache](https://docs.docker.com/build/cache/).

### 3.3 Production Dockerfile rules

| Rule | Why | In this project |
|---|---|---|
| Multi-stage build | Compilers, pip and caches stay in the builder stage; the runtime image is smaller with a smaller attack surface | `builder` creates `/opt/venv`; `runtime` copies only it |
| Slim or distroless base | Fewer packages = fewer CVEs and faster pulls | `python:3.13-slim` |
| Non-root numeric `USER` | A container escape as root is much worse; Kubernetes `runAsNonRoot` can only verify a numeric UID | `USER 10001:10001` |
| Exec-form `CMD`/`ENTRYPOINT` | The shell form runs `/bin/sh -c`, which does not forward SIGTERM: no graceful shutdown | `CMD ["uvicorn", …]` |
| `.dockerignore` | Smaller context; keeps `.env`, `.git` and local DB files out of the image | `.dockerignore` |
| No secrets in layers | Every layer is readable by anyone who can pull the image, even if a later layer deletes the file | Secrets arrive at runtime |
| `PYTHONUNBUFFERED=1` | Logs reach stdout immediately, not when a buffer fills | Set in runtime stage |
| Pin versions | Reproducible builds | Base tag; requirements ranges (lock with `uv lock` or `pip-compile` **[External]**) |

**Distroless** images (no shell, no package manager) shrink the attack surface further but make debugging harder (use `kubectl debug` with an ephemeral container) and tie you to the Python version the image ships. **uv** **[External]** is a fast alternative to pip in the builder stage (`uv sync --frozen --no-dev`). Docs: [multi-stage builds](https://docs.docker.com/build/building/multi-stage/), [Dockerfile reference](https://docs.docker.com/reference/dockerfile/).

### 3.4 Tags vs digests

**What it is.** A *tag* (`inventory-api:1.0.0`) is a movable pointer. A *digest* (`inventory-api@sha256:9f…`) identifies exact content and cannot change.

**Why it matters.** `:latest` tells you nothing about what is running and makes rollback impossible. Even a version tag can be overwritten unless the registry enforces **tag immutability** (an ECR repository setting). Best practice: tag with the version or git SHA for humans, deploy by digest for machines, and turn on immutability. A policy test in this project rejects `:latest`.

### 3.5 Docker Compose for local development

**What it is.** A YAML file that starts several containers (API, Postgres, Redis) on one network with one command: `docker compose up --build`.

**Why it matters.** It gives every developer the same dependencies, and it catches container-only bugs (non-root permissions, read-only filesystem, wrong host name) before Kubernetes does.

**How it works.** `depends_on` alone only waits for the container to *start*, not for Postgres to accept connections. Add a `healthcheck` (`pg_isready`) to the database and `condition: service_healthy` on the API. Service names are DNS names (`db:5432`). The top-level `version:` key is obsolete **[Legacy]**. Docs: [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/).

### 3.6 12-factor configuration and secrets

**What it is.** The [Twelve-Factor App](https://12factor.net/config) rule: configuration that varies between deploys lives in the environment, not the code. Logs go to stdout as an event stream (factor XI), and processes start fast and shut down gracefully (factor IX).

**How it works here.**

| Kind | Example | Where it lives |
|---|---|---|
| Non-secret config | `APP_LOG_LEVEL`, `APP_ENVIRONMENT` | ConfigMap → env vars |
| Secret | `APP_DATABASE_URL` (contains a password) | Secret, synced from AWS Secrets Manager |
| Build metadata | `APP_GIT_SHA` | Baked in at build (`ARG GIT_SHA`) |

`pydantic-settings` validates all of it at startup, so a typo fails fast instead of at the first request. Kubernetes Secrets are only base64-encoded; in production, keep the source of truth in **AWS Secrets Manager** or **SSM Parameter Store** and sync it with External Secrets Operator or the Secrets Store CSI driver **[External]**, and enable KMS envelope encryption for Secrets in etcd.

### 3.7 Kubernetes core objects

**What it is.** Kubernetes is a declarative control system. You submit desired state (YAML) to the API server; controllers continuously make reality match it.

| Object | Job | Remember |
|---|---|---|
| **Pod** | One or more containers sharing a network namespace and volumes | Ephemeral; never create bare Pods for services |
| **ReplicaSet** | Keeps N identical Pods running | Created and managed by a Deployment |
| **Deployment** | Declarative rollouts and rollbacks for stateless apps | `kubectl rollout undo` |
| **Service (ClusterIP)** | Stable virtual IP + DNS name in front of Pods chosen by a label selector | Only *ready* Pods are endpoints |
| **Service (LoadBalancer)** | Asks the cloud for an external load balancer (NLB on AWS) | One LB per Service: costly at scale |
| **Ingress** | HTTP routing (host/path) to Services through a controller | Annotations are controller-specific |
| **Gateway API** | Successor to Ingress: `GatewayClass`, `Gateway`, `HTTPRoute`; role-oriented and portable **[Current]** | ingress-nginx is retired; new platforms adopt Gateway API |
| **ConfigMap / Secret** | Configuration and sensitive values injected as env vars or files | Changing them does not restart Pods |
| **Namespace** | Scope for names, RBAC, quotas, Pod Security labels | One per app or team |
| **ServiceAccount** | Identity of a Pod for the Kubernetes API and, on EKS, for AWS | One per workload |
| **Role/RoleBinding** | RBAC: which verbs on which resources in a namespace | ClusterRole for cluster-wide |
| **HPA** | Scales replicas from metrics | Utilization is relative to *requests* |
| **PodDisruptionBudget** | Limits voluntary evictions (drains, upgrades) | `minAvailable` < replicas, or drains hang |

**Labels and selectors** glue everything together: the Deployment's Pod template carries `app.kubernetes.io/name: inventory-api`, and the Service, PDB and topology spread select on it. A mismatch produces a Service with no endpoints: the classic "503 from the ingress, pods look fine" bug.

A minimal Gateway API route, for comparison with the project's Ingress:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: inventory-api
  namespace: inventory
spec:
  parentRefs:
    - name: public-gateway        # a Gateway owned by the platform team
      namespace: gateways
  hostnames: ["inventory.example.com"]
  rules:
    - backendRefs:
        - name: inventory-api
          port: 80
```

Docs: [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/), [Services](https://kubernetes.io/docs/concepts/services-networking/service/), [Gateway API](https://kubernetes.io/docs/concepts/services-networking/gateway/).

### 3.8 Probes: startup, liveness, readiness

**What it is.** The kubelet calls HTTP endpoints (or runs commands) to decide what to do with a container.

| Probe | Question | On failure | This project |
|---|---|---|---|
| **startupProbe** | Has it finished booting? | Keeps waiting, then restarts after `failureThreshold × periodSeconds`; the other probes are disabled until it passes | `/health/live`, up to 60 s |
| **livenessProbe** | Is the process stuck beyond repair? | **Restarts** the container | `/health/live`, no dependency checks |
| **readinessProbe** | Should it receive traffic now? | **Removes** the Pod from Service endpoints (and ALB targets); no restart | `/health/ready`: `SELECT 1`, not draining |

**Why the difference matters.** If liveness checks the database, a 30-second DB failover makes Kubernetes restart *every* pod at once; when the DB returns, all pods are cold-starting together. That turns a blip into an outage (and a `CrashLoopBackOff`). Liveness must answer only "is this process alive?". Readiness answers "can I serve right now?" and *may* check critical dependencies, but beware: if every pod is unready, the Service has no endpoints and clients get 503 everywhere. That is usually the honest answer when the database is down. Docs: [configure probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/).

### 3.9 Resources: requests, limits, OOMKilled

**What it is.** `requests` is what the scheduler reserves on a node; `limits` is the hard ceiling enforced by cgroups.

| Resource | Exceeds request | Exceeds limit |
|---|---|---|
| CPU | Fine if the node has spare CPU | **Throttled** (slower, not killed) |
| Memory | Fine, but first to be evicted under node pressure | **OOMKilled** (exit code 137), container restarts |

Rules of thumb:

- Always set CPU and memory **requests**: the scheduler and the HPA depend on them.
- Always set a **memory limit**. Many teams set memory request = limit for predictable behavior (Guaranteed QoS when CPU also matches).
- CPU limits are debated: they cause throttling even when the node is idle. Many platform teams set CPU requests only. This project sets a generous CPU limit; its policy test requires only the memory limit.
- Size from measurements (`kubectl top pod`, Container Insights), not guesses. Python workers: memory scales with worker count and in-flight request size.

Docs: [resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).

### 3.10 Rollouts, HPA and PodDisruptionBudgets

**Rolling update.** `maxSurge: 1, maxUnavailable: 0` means "add one new pod, wait until it is *ready*, then remove one old pod". Capacity never drops, and a new version that never becomes ready stalls the rollout instead of replacing healthy pods. That is why readiness must be honest. `kubectl rollout undo deploy/inventory-api` returns to the previous ReplicaSet.

**HPA** (`autoscaling/v2`) computes `desired = ceil(current × currentMetric / target)`. With CPU at 140% of request on 2 pods and a 70% target, it asks for 4. It needs **metrics-server**, and CPU utilization is measured against the request (no request, no scaling). Custom metrics (requests per second, queue depth) come from Prometheus Adapter or **KEDA** **[External]**. A `scaleDown.stabilizationWindowSeconds` avoids flapping.

**Cluster scaling** is separate: HPA adds pods; **Karpenter** or Cluster Autoscaler adds nodes when pods are `Pending`. **EKS Auto Mode** **[Current] [Provider-specific]** manages nodes for you.

**PDB.** `minAvailable: 1` lets a node drain evict pods only while one stays available. If `minAvailable` equals the replica count, drains and cluster upgrades block forever. Docs: [HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/), [PDB](https://kubernetes.io/docs/tasks/run-application/configure-pdb/).

### 3.11 Graceful shutdown

**What it is.** The sequence when a pod is deleted (rollout, scale-down, drain):

```text
 t=0   Pod marked Terminating. In parallel:
       (a) endpoints controller removes it from the Service, the ALB
           controller starts deregistering the target (takes seconds)
       (b) kubelet runs preStop (sleep 10) — app still serving
 t=10  kubelet sends SIGTERM to PID 1 (uvicorn)
       uvicorn stops accepting, finishes in-flight requests (≤20 s)
       lifespan shutdown: health.begin_drain(), engine.dispose()
 t=40  terminationGracePeriodSeconds reached → SIGKILL if still alive
```

**Why it matters.** (a) and (b) race. Without `preStop`, the app may stop *before* the load balancer stops sending it traffic, and users see 502s during every deploy. The sleep covers the propagation delay. The grace period must exceed `preStop + app shutdown`; a policy test checks `40 > 10 + 20`. Exec-form `CMD` makes uvicorn PID 1 so it actually receives SIGTERM. The native `preStop: sleep` action **[Current, Kubernetes 1.30+]** works even in images without a `sleep` binary. Docs: [Pod termination](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination), [lifecycle hooks](https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/).

### 3.12 Pod security, RBAC and workload identity

- **Pod Security Admission** labels on the namespace (`enforce: restricted`) reject pods that run as root, allow privilege escalation or keep capabilities ([Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)).
- **securityContext:** `runAsNonRoot`, `readOnlyRootFilesystem` (mount an `emptyDir` at `/tmp`), `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`.
- **RBAC:** most application pods need *no* Kubernetes API access. Give each workload its own ServiceAccount and bind only what it needs ([RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)).
- **AWS access without keys** **[Provider-specific]**:
  - **IRSA** (IAM Roles for Service Accounts): an OIDC provider for the cluster, an IAM role whose trust policy allows `system:serviceaccount:inventory:inventory-api`, and an annotation on the ServiceAccount. The SDK exchanges the projected token for temporary credentials ([IRSA docs](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)).
  - **EKS Pod Identity** **[Current]**: simpler. Install the Pod Identity Agent add-on and create an association (cluster, namespace, ServiceAccount → role) with the EKS API. No OIDC provider and no annotation; the role trusts `pods.eks.amazonaws.com` ([Pod Identity docs](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)).
  - Never put access keys in Secrets or environment variables.

### 3.13 AWS building blocks

| Need | AWS service | Notes |
|---|---|---|
| Image registry | **ECR** | Tag immutability, scan on push (Inspector), lifecycle rules to delete old images |
| Run containers | **EKS** / **ECS** (EC2 or **Fargate**) | See decision table below |
| HTTP load balancing | **ALB** (L7) / NLB (L4) | AWS Load Balancer Controller creates ALBs from Ingress (and Gateway API in recent versions) |
| Relational DB | **RDS** / Aurora PostgreSQL | Multi-AZ, automated backups; RDS Proxy for connection pooling |
| Cache | **ElastiCache** (Redis OSS / Valkey) | Private subnets only |
| Secrets | **Secrets Manager** (rotation) / **SSM Parameter Store** (config, cheaper) | Encrypted with KMS |
| Network | **VPC**, subnets, route tables, NAT gateway, VPC endpoints | See below |
| Firewall | **Security groups** (stateful, per ENI) / NACLs (stateless, per subnet) | Reference SGs by ID, not CIDR |
| Identity | **IAM** roles and policies | One role per workload, least privilege |
| Logs, metrics, alarms | **CloudWatch** (Logs, Container Insights, Alarms) | Or ship to Datadog/Grafana (Unit 11) |
| DNS / TLS | Route 53 / ACM | ACM certificate on the ALB listener |

**Choosing a compute platform** ([AWS decision guide](https://docs.aws.amazon.com/decision-guides/latest/containers-on-aws-how-to-choose/choosing-aws-container-service.html)):

| Option | Choose when | Trade-off |
|---|---|---|
| **EKS** | Customer already runs Kubernetes; portability; many services; need the K8s ecosystem (operators, Helm, Argo CD) | Most power, most to operate (a Kubernetes minor upgrade about three times a year, add-ons) |
| **ECS on Fargate** | AWS-only shop, a handful of services, small team | Simple, no nodes; AWS-specific task definitions |
| **ECS on EC2** | Need GPUs, specific instance types, or lower cost at steady load | You manage the instances |
| **App Runner** | One web container, minimal ops | Few knobs; check its current status and features before proposing it |
| **Lambda** (+ API Gateway) | Spiky or low traffic, event-driven, short requests (≤15 min) | Cold starts, per-request pricing, connection management to RDS |

**VPC layout.** Public subnets hold only the ALB and NAT gateways. Pods, RDS and ElastiCache sit in **private subnets** across at least two Availability Zones. Security groups chain: `ALB-SG → app-SG :8000 → db-SG :5432`. In customer environments with no internet egress, private subnets reach AWS services through **VPC endpoints** (ECR `api` and `dkr`, S3 gateway for image layers, STS for IRSA, CloudWatch Logs, Secrets Manager). Missing endpoints are the top cause of `ImagePullBackOff` in private clusters ([private cluster requirements](https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html)).

### 3.14 Azure and GCP equivalents

| Concept | AWS | Azure | GCP |
|---|---|---|---|
| Managed Kubernetes | EKS | AKS | GKE |
| Serverless containers | ECS Fargate / App Runner | Container Apps | Cloud Run |
| Functions | Lambda | Azure Functions | Cloud Run functions |
| Registry | ECR | ACR | Artifact Registry |
| L7 load balancer | ALB | Application Gateway (for Containers) | Cloud Load Balancing |
| Managed Postgres | RDS / Aurora | Azure Database for PostgreSQL | Cloud SQL / AlloyDB |
| Managed Redis | ElastiCache | Azure Managed Redis | Memorystore |
| Secrets | Secrets Manager / SSM | Key Vault | Secret Manager |
| Pod → cloud identity | IRSA / EKS Pod Identity | Entra Workload ID | Workload Identity Federation for GKE |
| Network | VPC, SG | VNet, NSG | VPC, firewall rules |
| Observability | CloudWatch | Azure Monitor | Cloud Logging / Monitoring |
| IaC (native) | CloudFormation / CDK | Bicep / ARM | Infrastructure Manager |

The Kubernetes manifests stay almost identical across clouds. What changes: the ingress/gateway annotations, the identity annotation on the ServiceAccount, storage classes, and the registry URL. Keep those in overlays.

### 3.15 Infrastructure as code and policy as code

**What it is.** IaC declares cloud resources in versioned files and applies them with a tool that computes a plan (diff) first: **Terraform/OpenTofu** **[External]** (multi-cloud, HCL), **CloudFormation** (AWS-native YAML/JSON) and **CDK** (CloudFormation from TypeScript/Python).

**Why it matters.** Customer environments must be reproducible, reviewable and recoverable. "Someone clicked it in the console" cannot be reviewed or rebuilt.

```hcl
resource "aws_ecr_repository" "inventory" {
  name                 = "inventory-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_security_group_rule" "db_from_app" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.db.id
  source_security_group_id = aws_security_group.app.id
}
```

`terraform plan` in CI on every pull request, `apply` after review, remote state in S3 with locking. Docs: [Terraform](https://developer.hashicorp.com/terraform/docs), [CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html).

**Policy as code** checks manifests against rules automatically. This project does it with plain pytest and PyYAML. At scale: [kubeconform](https://github.com/yannh/kubeconform) validates against the Kubernetes schemas, [Conftest](https://www.conftest.dev/) (OPA/Rego) and [Kyverno](https://kyverno.io/) enforce policies in CI, and Kyverno or OPA Gatekeeper also enforce them as admission controllers inside the cluster **[External]**.

## 4. Application in a Real System

A manufacturing customer wants the inventory service from a pilot running in their AWS account. Constraints from their platform team: their existing EKS cluster, no public endpoints for internal tools, images only from their ECR, no long-lived AWS keys, and every manifest must pass their Kyverno policies.

- **Day 1:** discovery. Get the cluster version, ingress/gateway controller, namespace conventions, the policies they enforce, how secrets reach pods (External Secrets? CSI?), and the network path to RDS. Ask for a sandbox namespace.
- **Day 2:** container. Multi-stage, non-root image; compose stack for the team; policy tests added to CI so a violation fails your build before their admission controller rejects it.
- **Day 3:** manifests. Kustomize base plus an overlay per environment. Ingress `scheme: internal`, IRSA or Pod Identity role scoped to one secret ARN, probes and resources from a load test.
- **Day 4:** deploy to staging via their pipeline (Unit 7). Rolling update with a broken image on purpose to show the rollout stalls safely; `kubectl rollout undo` rehearsed.
- **Day 5:** hand-over: a runbook (how to check health, roll back, read logs), dashboards (Unit 11) and the IaC for the ECR repository, IAM role and security group rules.

Alternatives considered: ECS Fargate would be simpler to run, but the customer has already standardized on EKS, and fitting in beats introducing a second platform. Lambda was rejected because of steady traffic and database connection pooling.

## 5. Implementation

### 5.1 Liveness vs readiness in code

```python
@app.get("/health/live", tags=["ops"])
def live() -> dict[str, str]:
    return {"status": "alive"}           # no DB, no network

@app.get("/health/ready", tags=["ops"])
def ready(request: Request) -> JSONResponse:
    ok, details = check_ready(
        request.app.state.health, request.app.state.engine
    )
    return JSONResponse(details, status_code=200 if ok else 503)
```

```python
def check_ready(state, engine) -> tuple[bool, dict[str, str]]:
    if state.draining:
        return False, {"status": "draining"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False, {"status": "unavailable", "database": "down"}
    return True, {"status": "ready", "database": "ok"}
```

The readiness check never raises: a probe that times out or returns 500 is as bad as no probe. It also does not crash the app at startup when the database is unreachable; the app starts, stays *live*, and reports *not ready* until the database answers.

### 5.2 Graceful shutdown in the lifespan

```python
yield
# After SIGTERM: uvicorn stopped accepting connections and waited for
# in-flight requests (bounded by --timeout-graceful-shutdown).
health.begin_drain()
engine.dispose()
```

The `preStop` sleep does the heavy lifting of draining traffic; the app's job is to finish what it started and release connections cleanly so RDS does not accumulate half-open sessions.

### 5.3 The image: two stages, one non-root user

```dockerfile
FROM ${PYTHON_IMAGE} AS builder
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt

FROM ${PYTHON_IMAGE} AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
USER 10001:10001
CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "20", "--no-access-log"]
```

`--host 0.0.0.0` matters: uvicorn's default `127.0.0.1` is unreachable from outside the container, so probes and the Service would all fail.

### 5.4 The Deployment's operational contract

```yaml
strategy:
  rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
template:
  spec:
    terminationGracePeriodSeconds: 40   # > 10 preStop + 20 uvicorn
    containers:
      - name: api
        resources:
          requests: {cpu: 100m, memory: 128Mi}
          limits: {cpu: "1", memory: 256Mi}
        readinessProbe:
          httpGet: {path: /health/ready, port: http}
        livenessProbe:
          httpGet: {path: /health/live, port: http}
        lifecycle:
          preStop:
            sleep: {seconds: 10}
        securityContext:
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
```

### 5.5 Policy as code with pytest

```python
def test_service_selects_the_deployment_pods() -> None:
    deploy, svc = one("Deployment"), one("Service")
    pod_labels = deploy["spec"]["template"]["metadata"]["labels"]
    selector = svc["spec"]["selector"]
    assert selector.items() <= pod_labels.items()
    port_names = {p["name"] for p in containers()[0]["ports"]}
    for port in svc["spec"]["ports"]:
        assert port["targetPort"] in port_names


def test_shutdown_budget_fits_the_grace_period() -> None:
    pod = pod_spec()
    pre_stop = containers()[0]["lifecycle"]["preStop"]["sleep"][
        "seconds"
    ]
    cmd = final_cmd()                  # parsed from the Dockerfile
    graceful = int(cmd[cmd.index("--timeout-graceful-shutdown") + 1])
    assert pod["terminationGracePeriodSeconds"] > pre_stop + graceful
```

The second test crosses two files (Dockerfile and Deployment) that different people edit. That is exactly the kind of drift a reviewer misses and a test catches.

### 5.6 Commands you will actually type

```bash
kubectl -n inventory get pods -o wide
kubectl -n inventory describe pod <pod>      # Events: probes, OOM, pull
kubectl -n inventory logs <pod> --previous   # logs of the crashed run
kubectl -n inventory get endpointslices      # who receives traffic?
kubectl -n inventory rollout status deploy/inventory-api
kubectl -n inventory rollout undo deploy/inventory-api
kubectl -n inventory top pod                 # needs metrics-server
kubectl -n inventory get events --sort-by=.lastTimestamp
kubectl debug -it <pod> --image=busybox --target=api   # no shell? ok
```

## 6. How It Connects to the Rest of the System

```text
 Unit 6 deployment layer
   ├─ packages: the FastAPI services of U2/U5 (same create_app factory)
   ├─ config: pydantic-settings (U2) fed by ConfigMaps and Secrets
   ├─ data: RDS Postgres + migrations Job (U3), ElastiCache (U3)
   ├─ frontend: SPA build to S3 + CloudFront, /api → ALB (U5)
   ├─ CI/CD builds, scans, pushes and rolls out this image (U7)
   ├─ many services + retries/timeouts across the network (U8)
   ├─ LLM/RAG services deploy the same way; secrets for API keys (U9-10)
   ├─ JSON logs, metrics, traces, alerts built on these probes (U11)
   └─ runbooks, hand-over and customer environment constraints (U12)
```

## FDE Scenario 5 — "We deployed to the customer's EKS cluster and pods keep restarting"

**Stakeholder (customer platform lead, during a go-live window):** "Your pods have restarted 40 times in the last hour. Our on-call is getting paged. Fix it or we roll back the release."

- *Stay calm and scope:* agree on the immediate goal (stop the paging) and the decision deadline for rollback. Ask for read access to the namespace and the events if you do not have it. Offer to roll back first if the previous version was healthy: stability before diagnosis.
- *Investigate, cheapest signals first:*
  - `kubectl get pods`: `CrashLoopBackOff`, `OOMKilled` or `Running` with a rising restart count? Each points somewhere different.
  - `kubectl describe pod`: *Last State* reason and exit code (137 = SIGKILL, often OOM; 1 = app error), and Events such as "Liveness probe failed".
  - `kubectl logs --previous`: the crashed container's last words (a missing env var? a DB timeout?).
  - Compare with staging: the image digest, ConfigMap, Secret keys, resources and probe settings.
- *Typical causes in a customer cluster:*
  - the liveness probe checks the database, and their RDS is reachable only through a security group nobody added;
  - the memory limit was copied from a laptop guess and the customer's real data doubles memory use;
  - the startup is slower on their smaller nodes, and there is no startupProbe, so liveness kills the app before it boots;
  - their policy forces `readOnlyRootFilesystem`, and the app writes to a path without an `emptyDir`.
- *Contain:* roll back, or apply the minimal safe change (raise the memory limit, add a startupProbe, point liveness at `/health/live`) through their pipeline, not with `kubectl edit` in production.
- *What must be deterministic:* probe semantics, resource limits and the shutdown budget, all checked by policy tests in CI.
- *Prevent:* a pre-production environment that mirrors their policies and network; load-test-based sizing; Kyverno/Conftest rules in your own CI; an alert on restart rate.
- *Communicate:* a short written timeline (symptom, root cause, fix, verification, prevention). Separate facts from hypotheses, and say which change you made and when.

## Comprehension Questions

1. What isolates a container, and why can a kernel bug affect all containers on a host but not all VMs?
2. Why does copying `requirements.txt` before the application code speed up builds?
3. Why must the final Dockerfile `CMD` use the exec form?
4. What is the difference between a liveness and a readiness probe, and why must liveness not check the database?
5. What happens when a container exceeds its memory limit, and what when it exceeds its CPU limit?
6. With `maxSurge: 1, maxUnavailable: 0`, what happens if the new version never becomes ready?
7. Why is a `preStop` sleep needed even when the app handles SIGTERM correctly?
8. What do IRSA and EKS Pod Identity replace, and how does the pod get AWS credentials?

## Comprehension Answers

1. Linux namespaces (visibility) and cgroups (resource limits) isolate an ordinary process. All containers share the host kernel, so a kernel exploit crosses them. VMs each run their own kernel behind a hypervisor.
2. Layers are cached while the instruction and all previous layers are unchanged. Dependencies change rarely, code changes often; putting code last means only the cheap `COPY app` layer rebuilds.
3. The shell form runs the command under `/bin/sh -c`, which becomes PID 1 and does not forward SIGTERM. The app never shuts down gracefully and gets SIGKILL after the grace period.
4. Liveness failure restarts the container; readiness failure only removes the pod from load balancing. A database outage would make liveness restart every pod at once, turning a blip into a crash loop. Readiness can reflect the dependency without killing anything.
5. Memory over the limit: the kernel OOM-kills the container (exit 137, reason OOMKilled) and it restarts. CPU over the limit: the container is throttled (runs slower) but not killed.
6. The new pod is never counted as available, so no old pod is removed. The rollout stalls (and eventually reports `ProgressDeadlineExceeded`) while the old version keeps serving at full capacity. You then roll back.
7. Removing the pod from endpoints and deregistering the ALB target happen in parallel with the shutdown and take seconds. Without the sleep, the app can stop before traffic stops arriving, which produces 502s during every deploy.
8. They replace long-lived access keys. The pod's ServiceAccount is linked to an IAM role (by annotation for IRSA, by an EKS association for Pod Identity); the AWS SDK exchanges a projected, short-lived token for temporary role credentials.

## Interview Questions — Theory-Based

**Q1. How would you write a production Dockerfile for a Python API?**

- *Strong answer:* multi-stage (builder installs dependencies into a venv or wheels; runtime copies only those), a slim or distroless base pinned by version, dependency manifest copied before code for caching, a non-root numeric `USER`, exec-form `CMD` binding `0.0.0.0`, `PYTHONUNBUFFERED`, `.dockerignore`, no secrets in any layer, version and git SHA as labels or env, image scanned in CI.
- *What it tests:* practical container knowledge and security habits.
- *Follow-up:* "The image is 1.2 GB. What do you check?" (`docker history` for big layers; build tools in the final stage; a full base image; caches not cleaned; the `.git` folder in the build context.)

**Q2. Explain liveness, readiness and startup probes.**

- *Strong answer:* startup gates the others for slow boots; liveness restarts a stuck process and must not depend on external systems; readiness controls traffic and may check critical dependencies and a draining flag. Give the cascading-restart failure as the reason for the separation, and mention timeouts and thresholds.
- *What it tests:* operational judgment, not just YAML.
- *Follow-up:* "Should readiness check a downstream payment API?" (Usually no: degrade that feature instead; checking every dependency makes the whole service unavailable when one non-critical dependency is down.)

**Q3. What are requests and limits, and how do you set them?**

- *Strong answer:* requests drive scheduling and HPA utilization; limits are cgroup ceilings. Memory over the limit is OOMKilled, CPU over the limit is throttled. Measure under load, set memory limit near observed peak plus headroom, CPU requests from the steady state, and treat CPU limits as a deliberate choice because they cause throttling.
- *Follow-up:* "Pods are slow but CPU usage looks low." (CPU throttling: check `container_cpu_cfs_throttled_periods_total`.)

**Q4. How does a zero-downtime deployment work on Kubernetes?**

- *Strong answer:* rolling update with `maxUnavailable: 0`, honest readiness, `preStop` sleep to cover endpoint and load-balancer propagation, SIGTERM handled by the app, a grace period larger than the sum, a PDB for drains, backward-compatible database migrations (expand and contract), and a rollback path (`rollout undo` or redeploy the previous digest).
- *What it tests:* whether you know the race between deregistration and shutdown.

**Q5. EKS, ECS Fargate or Lambda: how do you choose?**

- *Strong answer:* start from constraints. What the customer already runs and can operate; the number of services; traffic shape; latency and cold-start tolerance; portability requirements; team skills; cost at expected load. EKS for Kubernetes shops and many services, Fargate for simple AWS-native container workloads, Lambda for spiky event-driven work. Fitting the customer's platform usually beats the "best" option.
- *Follow-up:* "What breaks when you move a FastAPI app to Lambda?" (Cold starts, database connection storms without RDS Proxy, the 15-minute limit, request size limits, no background threads after the response.)

**Q6. How do pods get access to AWS services securely?**

- *Strong answer:* IRSA or EKS Pod Identity give each ServiceAccount an IAM role with temporary credentials; policies are least-privilege (specific actions on specific ARNs); no static keys. Network access is separate: security groups and VPC endpoints.
- *Follow-up:* "AccessDenied, but the role has the policy." (Wrong ServiceAccount name or namespace in the trust policy, pod not restarted after the annotation, SDK too old, or a node-role fallback.)

**Q7. How do you handle secrets in Kubernetes?**

- *Strong answer:* Kubernetes Secrets are base64, not encryption. Keep the source of truth in Secrets Manager or Vault, sync with External Secrets Operator or the CSI driver, encrypt etcd with KMS, restrict `get secrets` via RBAC, never bake secrets into images or commit them, rotate, and prefer IAM-based auth (for example, RDS IAM authentication) where possible.

**Q8. What is the difference between Ingress and Gateway API?**

- *Strong answer:* Ingress is a single resource whose advanced features live in controller-specific annotations. Gateway API splits responsibilities (`GatewayClass` for the infrastructure provider, `Gateway` for the platform team, `HTTPRoute` for app teams), supports header matching, traffic splitting and more protocols portably, and is the current direction; ingress-nginx is retired.

## Interview Questions — Application / Experience-Based

**A1. Tell me about a service you containerized and deployed.**

- *Cover:* the starting point, the Dockerfile decisions, the platform (EKS, ECS, other), configuration and secrets, health checks, rollout and rollback, and one problem you hit.
- *Structure:* situation → constraints → design → deploy → verification → result → lesson.
- *Personalize:* "`<<personalize: service and users>>` ran on `<<platform>>`. I built `<<image approach>>`, configured `<<config/secrets mechanism>>`, and set probes to `<<semantics>>`. The problem was `<<issue>>`; I fixed it by `<<fix>>`. Result: `<<metric: deploy time, incidents, image size>>`."
- *Lab-honest version:* "In a project I built and tested a FastAPI service with a multi-stage non-root image, a compose stack with Postgres, and Kubernetes manifests with probes, resources, HPA, PDB and IRSA. Policy tests in pytest check the manifests, and I ran it on a local kind cluster. I have not operated it under production traffic."
- *Follow-ups:* "How did you size resources?" "What happens to in-flight requests during a deploy?"

**A2. Describe a time a deployment failed. How did you diagnose it?**

- *Cover:* symptom, the signals you read in order (pod status, describe, previous logs, events, metrics), root cause, fix, and the prevention you added.
- *Structure:* symptom → triage → root cause → fix → prevention.
- *Personalize:* "`<<personalize: what failed, when>>`. `kubectl describe` showed `<<reason>>`. The cause was `<<cause>>`. We `<<rollback or fix>>` and added `<<test/alert/policy>>`."
- *Lab-honest version:* "In lab work I reproduced the common failures on purpose: an OOMKilled pod with a tiny memory limit, a crash loop from a liveness probe on the database, and a Service with no endpoints from a label mismatch. I can walk you through how each shows up."
- *Follow-ups:* "How do you decide between rollback and fix-forward?"

**A3. How have you worked within a customer's cloud or security constraints?**

- *Cover:* the constraint (private networking, approved base images, admission policies, no internet egress), how you discovered it early, and how you adapted the design.
- *Structure:* constraint → discovery → adaptation → verification with their team.
- *Personalize:* "`<<personalize: customer/environment>>` required `<<constraint>>`. I `<<adaptation: VPC endpoints, internal ALB, policy tests>>` and verified with `<<their security/platform team>>`."
- *Lab-honest version:* "I have not worked inside a customer account yet. My approach: run discovery on cluster version, ingress controller, policies, secret flow and network path before writing manifests, then mirror their policies in my CI."
- *Follow-ups:* "What do you ask a customer platform team on day one?"

**A4. How have you made a deployment reproducible?**

- *Cover:* IaC for cloud resources, versioned manifests (kustomize/Helm), images pinned by digest, CI that builds once and promotes, environment differences kept in overlays.
- *Personalize:* "`<<personalize: tool, scope>>`. Before, `<<problem: console changes, drift>>`; after, `<<result>>`."
- *Lab-honest version:* "In this guide's project the manifests are a kustomize base with a dev overlay, validated by policy tests and kubeconform, and the chapter shows the Terraform for the registry and security groups."
- *Follow-ups:* "How do you detect drift?"

**A5. Tell me about a time you had to choose a hosting platform.**

- *Cover:* the options, the decision criteria (existing platform, team skills, traffic, cost, compliance), the decision and what you would revisit.
- *Personalize:* "`<<personalize: options>>`, we chose `<<choice>>` because `<<reasons>>`. Looking back, `<<lesson>>`."
- *Lab-honest version:* use the decision table in §3.13 and say which constraints would move you between EKS, Fargate and Lambda.
- *Follow-ups:* "What would make you migrate later?"

## Troubleshooting Scenarios

**T1. Pods are in `CrashLoopBackOff`.**

```text
SYMPTOM     STATUS CrashLoopBackOff, restarts climbing
CHECK       kubectl describe pod → Last State reason + exit code
            kubectl logs <pod> --previous
            Events: "Liveness probe failed"? "Back-off restarting"?
CAUSES      app exits at startup (missing env var, bad DATABASE_URL);
            liveness depends on DB; no startupProbe on a slow boot;
            read-only root FS and app writes outside /tmp
CONFIRM     run the image locally with the same env and
            --read-only; compare ConfigMap/Secret keys to staging
FIX         fix config; liveness → /health/live; add startupProbe;
            mount emptyDir for writable paths
PREVENTION  policy tests for probe paths; startup config validation
```

**T2. Pods restart with exit code 137 and reason `OOMKilled`.**

```text
SYMPTOM     Last State: Terminated, Reason: OOMKilled, Exit 137
CHECK       kubectl top pod; Container Insights memory vs limit;
            number of uvicorn/gunicorn workers; large responses
CAUSES      limit below real peak; memory leak; too many workers
            per container; loading a big file/result set in memory
CONFIRM     memory graph climbs to the limit before each restart
FIX         raise limit from measured peak + headroom; stream or
            paginate; fewer workers per pod, more pods
PREVENTION  load test before go-live; alert at 80% of limit
```

**T3. Pods stuck in `ImagePullBackOff` in a private cluster.**

```text
SYMPTOM     ErrImagePull / ImagePullBackOff
CHECK       describe pod Events: "not found", "unauthorized",
            "i/o timeout"? exact image URI and tag/digest
CAUSES      tag does not exist (typo, not pushed); node role lacks
            ECR read; private subnets with no NAT and no VPC
            endpoints (ecr.api, ecr.dkr, S3 gateway); cross-region
            or cross-account repository without a repo policy
CONFIRM     aws ecr describe-images --image-ids imageTag=1.0.0;
            check route tables and VPC endpoints for the subnets
FIX         push/correct the tag; attach AmazonEC2ContainerRegistry-
            ReadOnly (or equivalent) to the node role; add endpoints
PREVENTION  deploy by digest from CI; IaC for endpoints and policies
```

**T4. Users get 502/503 errors from the ALB during every deploy.**

```text
SYMPTOM     error spike for ~10-30 s on each rollout
CHECK       preStop present? terminationGracePeriodSeconds vs
            preStop + app shutdown; ALB deregistration delay;
            readiness probe settings; maxUnavailable
CAUSES      app stops before the target is deregistered; shell-form
            CMD so SIGTERM never reaches the app (SIGKILL); new pods
            marked ready before they can serve
FIX         preStop sleep 10; exec-form CMD; grace period > sum;
            maxUnavailable 0; honest readiness
PREVENTION  policy test for the shutdown budget; synthetic traffic
            during a staging rollout
```

**T5. The Service returns 503 although all pods are `Running`.**

```text
SYMPTOM     ingress/ALB 503 "no healthy upstream"; pods Running
CHECK       kubectl get endpointslices -l kubernetes.io/service-name=
            inventory-api; pod READY column (0/1?); Service selector
            vs pod labels; targetPort name vs container port name
CAUSES      label/selector mismatch; readiness failing (DB down);
            targetPort points to a non-existent port; ALB health
            check path wrong
FIX         align labels/ports; fix the dependency or readiness
PREVENTION  policy test: Service selector ⊆ pod labels, ports exist
```

**T6. The app gets `AccessDenied` from Secrets Manager on EKS.**

```text
SYMPTOM     botocore AccessDenied / "not authorized to perform
            secretsmanager:GetSecretValue"
CHECK       pod's serviceAccountName; SA annotation or Pod Identity
            association; role trust policy (namespace:name); env
            AWS_ROLE_ARN in the pod (IRSA); role policy resource ARN
CAUSES      wrong SA or namespace in the trust policy; pod created
            before the annotation (restart needed); policy scoped to
            a different secret ARN; KMS key policy missing decrypt
CONFIRM     aws sts get-caller-identity from inside the pod
FIX         correct trust/association; restart pods; fix ARNs/KMS
PREVENTION  IaC for role + association; a startup check that logs
            the caller identity once
```

## Unit Practice Project — Deployable Inventory API

### Project Goal

Take a small FastAPI service and make it **deployable and operable**:

- 12-factor configuration, JSON logs on stdout and build metadata at `/version`;
- honest health endpoints and graceful shutdown;
- a multi-stage, non-root image and a compose stack with Postgres 18;
- Kubernetes manifests for EKS with probes, resources, security context, rolling updates, HPA, PDB and IRSA;
- policy tests that check the Dockerfile, compose file and manifests without Docker or a cluster.

### Architecture

```text
 app/                                  k8s/base/ (kustomize)
  main.py  create_app()                 namespace (PSA restricted)
   ├ lifespan: engine, schema,          serviceaccount (IRSA role)
   │           begin_drain() on stop    configmap  secret.example
   ├ /health/live   always 200          deployment (2, probes,
   ├ /health/ready  SELECT 1 / 503        resources, preStop, non-root)
   ├ /version       version + git_sha   service (ClusterIP :80→http)
   └ /items  GET POST /items/{id}       ingress (ALB annotations)
  health.py  HealthState, check_ready   hpa (v2, CPU 70%)  pdb (min 1)
  config.py  Settings (APP_*)          k8s/overlays/dev (kind)
  logging_config.py  JSON → stdout     Dockerfile  docker-compose.yml
 tests/  app tests + policy tests (PyYAML, Dockerfile parser)
```

### Requirements

1. Settings come from `APP_*` environment variables (`database_url`, `log_level`, `environment`, `version`, `git_sha`, `create_schema`).
2. `GET /health/live` returns 200 whenever the process runs, even if the database is down.
3. `GET /health/ready` returns 200 after `SELECT 1` succeeds, and 503 when the database is unreachable or the app is draining.
4. The lifespan shutdown marks the app as draining before disposing of the engine. Startup does not crash when the database is unreachable.
5. `GET /version` returns version, git SHA and environment.
6. `POST /items` (201, 409 on duplicate SKU, 422 on invalid input), `GET /items`, `GET /items/{id}` (404 if missing).
7. Logs are one JSON object per line on stdout; probe requests are not logged.
8. The Dockerfile is multi-stage on `python:3.13-slim`, runs as a numeric non-root user, exposes 8000 and uses an exec-form `CMD` with `--factory` and a graceful-shutdown timeout.
9. Compose starts Postgres 18 with a health check, and the API waits for `service_healthy`.
10. The manifests satisfy every policy test: requests and limits, correct probe paths, non-root and read-only root, pinned image, matching selectors and ports, HPA targeting the Deployment, PDB below minimum replicas, shutdown budget, config/secret separation, IRSA ServiceAccount.

### Technical Requirements

- Python 3.12+, FastAPI, SQLAlchemy 2.1, pydantic-settings, uvicorn; psycopg 3 for Postgres.
- PyYAML for policy tests. No Docker daemon or cluster is needed for `pytest`.
- To run it for real: Docker Engine with Compose v2, kind or minikube, kubectl 1.30+; for AWS: aws CLI v2, eksctl, an EKS cluster with the AWS Load Balancer Controller and metrics-server.

### Project Structure

{{tree projects/unit06-cloud/solution}}

### Step-by-Step Implementation

1. **Run the starter's tests.** `pytest -q` shows 24 passed, 11 failed. The failures are your specification.
   - *Why:* see which behaviors and policies are missing before changing anything.
2. **TODO 1: readiness logic in `app/health.py`.** Draining first, then `SELECT 1`, catching `SQLAlchemyError`.
   - *Test:* `pytest -q tests/test_health.py -k ready`.
3. **TODO 2: draining on shutdown in `app/main.py`.**
   - *Test:* `pytest -q -k shutdown`.
4. **TODO 3–4: multi-stage Dockerfile and non-root user.**
   - *Test:* `pytest -q tests/test_container_policy.py`. If you have Docker: `docker build -t inventory-api:dev .` and `docker run --rm inventory-api:dev id` prints `uid=10001`.
5. **TODO 5–6: probes and resources in `deployment.yaml`.**
   - *Test:* `pytest -q tests/test_k8s_policy.py -k "probes or requests"`.
6. **TODO 7: complete `hpa.yaml`.**
   - *Test:* `pytest -q -k pdb` (it reads the HPA's minimum replicas).
7. **TODO 8–9: write the two policy tests.** Then break the manifest on purpose (set the image to `:latest`, rename the HPA target) and make sure each test fails.
8. **Finish:** `pytest -q && ruff check . && mypy`. Optionally `kustomize build k8s/base | kubeconform -strict -summary`.

### Starter Code

{{file projects/unit06-cloud/starter/app/health.py}}

{{file projects/unit06-cloud/starter/Dockerfile}}

{{file projects/unit06-cloud/starter/k8s/base/deployment.yaml}}

The starter also has TODOs in `app/main.py` (draining on shutdown), `k8s/base/hpa.yaml` (target and metric) and `tests/test_k8s_policy.py` (two policy tests). The task table is in the starter `README.md`.

### Practice Tasks

1. **Normal behavior:** start with compose; create items; check `/version` shows the git SHA you passed at build time.
2. **Failure behavior:**
   - `docker compose stop db`: ready → 503, live → 200; start it again and readiness recovers without a restart;
   - send `docker compose kill -s SIGTERM api` during a slow request and watch the JSON shutdown logs.
3. **Kubernetes behavior (kind):**
   - set the memory limit to `40Mi` and watch `OOMKilled`;
   - point liveness at `/health/ready` and break the DB URL: watch the crash loop, then fix it;
   - deploy an image tag that does not exist with `maxUnavailable: 0` and confirm the old pods keep serving; `rollout undo`.
4. **Security:**
   - `kubectl exec` into a pod and try to write to `/srv`: it fails (read-only root);
   - remove `runAsNonRoot` and change `USER` to root: the namespace's Pod Security Admission rejects the pod.
5. **Extend:**
   - add a migration `Job` (Alembic) and set `APP_CREATE_SCHEMA=false` everywhere;
   - replace the Ingress with a Gateway API `HTTPRoute`;
   - replace `secret.example.yaml` with an External Secrets `ExternalSecret` that reads from Secrets Manager;
   - add a policy test that every image is referenced by digest in a `prod` overlay.

### Hints

1. `with engine.connect() as conn: conn.execute(text("SELECT 1"))` raises a subclass of `SQLAlchemyError` when the database is unreachable. Catch that, not `Exception`.
2. The shutdown code runs *after* `yield` in the lifespan; `health` is already in scope as a closure variable.
3. In the runtime stage, `ENV PATH="/opt/venv/bin:${PATH}"` makes `uvicorn` resolve from the copied venv.
4. Use a numeric `USER 10001:10001`; a user *name* cannot be verified by `runAsNonRoot` and the pod is rejected.
5. Probes use `port: http` (the named container port), so renaming the number later does not break them.
6. For the image test, split on the last `/` before looking for `:`; a registry host such as `localhost:5000/app` contains a colon but no tag.

### Expected Behavior

```text
GET  /health/live                       → 200 {"status":"alive"}
GET  /health/ready                      → 200 {"status":"ready",…}
GET  /health/ready   (DB down)          → 503 {"database":"down",…}
GET  /health/ready   (after SIGTERM)    → 503 {"status":"draining"}
GET  /version                           → {"version":"1.0.0",
                                           "git_sha":"3f9c2ab",…}
POST /items {"sku":"BOLT-M6","name":"Bolt","quantity":40}  → 201
POST /items (same sku)                  → 409
POST /items {"sku":"","quantity":-1}    → 422
GET  /items/999                         → 404
stdout: {"ts":"…","level":"INFO","logger":"access","msg":"request",
         "method":"POST","path":"/items","status":201,"ms":8.9}
```

### Testing Requirements

- **App (13):** live, ready, ready 503 with the DB down, live while the DB is down, draining, shutdown marks draining, version, settings from env, JSON logs, items CRUD, 404, 409, 422.
- **Kubernetes policy (14, one parametrized per container):** kustomization lists every file, labels and namespace, requests and limits, probe paths, non-root/read-only, pinned image, Service ↔ Deployment, HPA target, PDB, rolling update, shutdown budget, config/secret separation, IRSA ServiceAccount, dev overlay.
- **Container policy (8):** multi-stage, slim pinned base, non-root user, exec-form `CMD`, `EXPOSE`, `.dockerignore`, compose health dependency, compose database URL.

```bash
pytest -q && ruff check . && ruff format --check . && mypy
```

### Final Runnable Solution

{{files projects/unit06-cloud/solution}}

### How to Run

Automated verification needs only Python. The container and cluster commands below run on your machine.

```bash
cd projects/unit06-cloud/solution
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q && ruff check . && mypy

# 1. Local container stack (Docker Engine + Compose v2)
GIT_SHA=$(git rev-parse --short HEAD) docker compose up --build -d
curl -s localhost:8000/health/ready && curl -s localhost:8000/version
docker compose logs -f api              # JSON lines
docker compose down -v

# 2. Local Kubernetes (kind)
docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD) \
  -t inventory-api:dev .
kind create cluster --name inventory
kind load docker-image inventory-api:dev --name inventory
kubectl apply -k k8s/overlays/dev
kubectl -n inventory rollout status deploy/inventory-api
kubectl -n inventory port-forward svc/inventory-api 8080:80
curl -s localhost:8080/health/ready
```

On AWS **[Provider-specific]** (replace account, region and names; needs an EKS cluster with the AWS Load Balancer Controller and metrics-server):

```bash
export AWS_REGION=us-east-1 ACCOUNT=111122223333
REPO=$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/inventory-api
aws ecr create-repository --repository-name inventory-api \
  --image-tag-mutability IMMUTABLE \
  --image-scanning-configuration scanOnPush=true
aws ecr get-login-password | docker login --username AWS \
  --password-stdin $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
docker build --platform linux/amd64 -t $REPO:1.0.0 .
docker push $REPO:1.0.0

# IAM role for the ServiceAccount (IRSA) via eksctl:
eksctl create iamserviceaccount --cluster demo \
  --namespace inventory --name inventory-api \
  --attach-policy-arn arn:aws:iam::$ACCOUNT:policy/inventory-read \
  --approve --override-existing-serviceaccounts
# or EKS Pod Identity:
# aws eks create-pod-identity-association --cluster-name demo \
#   --namespace inventory --service-account inventory-api \
#   --role-arn arn:aws:iam::$ACCOUNT:role/inventory-api

kubectl apply -k k8s/base       # after editing the image, ARNs, host
kubectl -n inventory get ingress inventory-api   # ALB DNS name
```

`--platform linux/amd64` matters when you build on an Apple Silicon laptop for x86 nodes; otherwise pods fail with `exec format error`. Use Graviton (arm64) nodes or a multi-arch build (`docker buildx build --platform linux/amd64,linux/arm64`) to avoid the mismatch.

### Verify the Solution

1. `pytest -q`: **35 passed** (13 app, 14 Kubernetes policy, 8 container policy); `ruff check .`, `ruff format --check .` and `mypy` clean.
2. The starter: **24 passed, 11 failed** until TODOs 1–9 are done.
3. Optional schema check: `kustomize build k8s/base | kubeconform -strict -summary` reports 9 valid resources; the dev overlay reports 8 (no Ingress).
4. Compose: `/health/ready` is 200; after `docker compose stop db` it is 503 while `/health/live` stays 200.
5. kind: `kubectl -n inventory get pods` shows two pods `1/1` ready; during `kubectl -n inventory rollout restart deploy/inventory-api`, `kubectl get pods -w` shows a new pod become ready before each old one terminates.
6. `kubectl -n inventory exec deploy/inventory-api -- id` prints `uid=10001`.

### Project Interview Debrief

1. **Why does `/health/live` not check the database?**
   Because liveness failure restarts the container. A database outage would restart every pod at once and create a crash loop that outlasts the outage. Only readiness reflects dependencies, and it only removes pods from traffic.
2. **Why both a `preStop` sleep and graceful shutdown in the app?**
   They solve different problems. The sleep covers the delay before Kubernetes and the ALB stop sending new requests; the app's graceful shutdown finishes in-flight requests and closes database connections. The grace period must cover both, and a policy test enforces it.
3. **Why test YAML with pytest instead of only running `kubectl apply --dry-run`?**
   A dry run checks syntax and schema; it does not know your rules (probe paths, non-root, pinned images, selectors matching, PDB below the minimum replica count). Policy tests encode those rules, run in milliseconds in CI and fail with a clear message. In larger organizations the same rules move to Conftest or Kyverno.
4. **What changes when you deploy this into a customer's private EKS cluster?**
   An internal ALB scheme, their ECR and possibly their approved base image, VPC endpoints for ECR/S3/STS/Logs/Secrets Manager if there is no egress, their secret delivery mechanism, an IRSA or Pod Identity role scoped to the exact secret ARN, and compliance with their admission policies. Those differences go in an overlay; the image stays the same.
5. **What would you add before production?**
   A migration Job and `APP_CREATE_SCHEMA=false`, deploy by digest from CI with image scanning and signing, External Secrets instead of a Secret manifest, NetworkPolicies, Gateway API if the platform supports it, dashboards and alerts on restarts, 5xx rate and latency (Unit 11), and a load test to set resources and HPA targets.
