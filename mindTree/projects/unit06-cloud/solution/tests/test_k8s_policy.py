"""Policy as code: rules every manifest must satisfy before it ships.

The same idea at scale: kubeconform (schema), Conftest/OPA or Kyverno
(policy), run in CI and as admission control in the cluster.
"""

import pytest
import yaml

from tests.manifests import (
    BASE,
    ROOT,
    Doc,
    containers,
    final_cmd,
    k8s_docs,
    one,
    pod_spec,
)


def test_every_manifest_is_listed_in_kustomization() -> None:
    kust = yaml.safe_load((BASE / "kustomization.yaml").read_text())
    on_disk = {
        p.name
        for p in BASE.glob("*.yaml")
        if p.name != "kustomization.yaml"
    }
    assert set(kust["resources"]) == on_disk


def test_every_object_has_name_label_and_namespace() -> None:
    for doc in k8s_docs():
        meta = doc["metadata"]
        if doc["kind"] != "Namespace":
            assert meta["namespace"] == "inventory", meta["name"]
            assert "app.kubernetes.io/name" in meta["labels"]


@pytest.mark.parametrize("box", containers(), ids=lambda c: c["name"])
def test_containers_have_requests_and_limits(box: Doc) -> None:
    res = box.get("resources", {})
    assert {"cpu", "memory"} <= set(res.get("requests", {}))
    # A memory limit is mandatory (OOMKilled beats a starved node).
    # CPU limits are a team choice: they cause throttling.
    assert "memory" in res.get("limits", {})


def test_probes_point_to_the_right_endpoints() -> None:
    box = containers()[0]
    assert box["livenessProbe"]["httpGet"]["path"] == "/health/live"
    assert box["readinessProbe"]["httpGet"]["path"] == "/health/ready"
    # Startup must not depend on the database either.
    assert box["startupProbe"]["httpGet"]["path"] == "/health/live"


def test_pod_runs_as_non_root_with_read_only_root() -> None:
    pod = pod_spec()
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["securityContext"]["runAsUser"] != 0
    for box in containers():
        ctx = box["securityContext"]
        assert ctx["readOnlyRootFilesystem"] is True
        assert ctx["allowPrivilegeEscalation"] is False
        assert ctx["capabilities"]["drop"] == ["ALL"]


def test_images_are_pinned_not_latest() -> None:
    for box in containers():
        image: str = box["image"]
        name = image.rsplit("/", 1)[-1]
        assert "@sha256:" in image or ":" in name, f"untagged {image}"
        assert not image.endswith(":latest"), image


def test_service_selects_the_deployment_pods() -> None:
    deploy, svc = one("Deployment"), one("Service")
    pod_labels = deploy["spec"]["template"]["metadata"]["labels"]
    selector = svc["spec"]["selector"]
    assert selector.items() <= pod_labels.items()
    assert deploy["spec"]["selector"]["matchLabels"] == selector
    port_names = {p["name"] for p in containers()[0]["ports"]}
    for port in svc["spec"]["ports"]:
        assert port["targetPort"] in port_names


def test_hpa_targets_the_deployment() -> None:
    hpa, deploy = one("HorizontalPodAutoscaler"), one("Deployment")
    assert hpa["apiVersion"] == "autoscaling/v2"
    ref = hpa["spec"]["scaleTargetRef"]
    assert ref["kind"] == "Deployment"
    assert ref["name"] == deploy["metadata"]["name"]
    assert 2 <= hpa["spec"]["minReplicas"] <= hpa["spec"]["maxReplicas"]


def test_pdb_matches_pods_and_leaves_room_to_drain() -> None:
    pdb, hpa = one("PodDisruptionBudget"), one("HorizontalPodAutoscaler")
    pod_labels = one("Deployment")["spec"]["template"]["metadata"]["labels"]
    assert pdb["spec"]["selector"]["matchLabels"].items() <= (
        pod_labels.items()
    )
    # minAvailable must be below the minimum replica count, or a node
    # drain can never evict a pod and cluster upgrades hang.
    assert pdb["spec"]["minAvailable"] < hpa["spec"]["minReplicas"]


def test_rolling_update_keeps_full_capacity() -> None:
    strategy = one("Deployment")["spec"]["strategy"]
    assert strategy["type"] == "RollingUpdate"
    assert strategy["rollingUpdate"]["maxUnavailable"] == 0
    assert strategy["rollingUpdate"]["maxSurge"] >= 1


def test_shutdown_budget_fits_the_grace_period() -> None:
    pod = pod_spec()
    pre_stop = containers()[0]["lifecycle"]["preStop"]["sleep"]["seconds"]
    cmd = final_cmd()
    graceful = int(cmd[cmd.index("--timeout-graceful-shutdown") + 1])
    assert pod["terminationGracePeriodSeconds"] > pre_stop + graceful


def test_config_and_secrets_are_separated() -> None:
    config = one("ConfigMap")["data"]
    assert not any(
        word in key
        for key in config
        for word in ("PASSWORD", "SECRET", "TOKEN", "DATABASE_URL")
    )
    refs = containers()[0]["envFrom"]
    assert {"configMapRef", "secretRef"} == {k for r in refs for k in r}


def test_pods_use_the_irsa_service_account() -> None:
    sa = one("ServiceAccount")
    assert "eks.amazonaws.com/role-arn" in sa["metadata"]["annotations"]
    pod = pod_spec()
    assert pod["serviceAccountName"] == sa["metadata"]["name"]


def test_dev_overlay_builds_on_base() -> None:
    path = ROOT / "k8s" / "overlays" / "dev" / "kustomization.yaml"
    kust = yaml.safe_load(path.read_text())
    assert "../../base" in kust["resources"]
    for patch in kust["patches"]:
        if "path" in patch:
            assert (path.parent / patch["path"]).is_file()
