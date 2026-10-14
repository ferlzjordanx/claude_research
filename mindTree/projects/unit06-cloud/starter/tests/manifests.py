"""Loaders shared by the policy tests (no Docker or cluster needed)."""

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "k8s" / "base"
Doc = dict[str, Any]


def k8s_docs() -> list[Doc]:
    docs: list[Doc] = []
    for path in sorted(BASE.glob("*.yaml")):
        if path.name == "kustomization.yaml":
            continue
        docs += [d for d in yaml.safe_load_all(path.read_text()) if d]
    return docs


def one(kind: str) -> Doc:
    matches = [d for d in k8s_docs() if d["kind"] == kind]
    assert len(matches) == 1, f"expected exactly one {kind}"
    return matches[0]


def pod_spec() -> Doc:
    spec: Doc = one("Deployment")["spec"]["template"]["spec"]
    return spec


def containers() -> list[Doc]:
    pod = pod_spec()
    return list(pod["containers"]) + list(pod.get("initContainers", []))


def dockerfile() -> list[tuple[str, str]]:
    """Return (INSTRUCTION, arguments) pairs, continuations joined."""
    text = (ROOT / "Dockerfile").read_text()
    joined = text.replace("\\\n", " ")
    result: list[tuple[str, str]] = []
    for line in joined.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        instruction, _, args = line.partition(" ")
        result.append((instruction.upper(), args.strip()))
    return result


def stages() -> list[list[tuple[str, str]]]:
    """Split the Dockerfile into build stages at each FROM."""
    out: list[list[tuple[str, str]]] = []
    for instruction, args in dockerfile():
        if instruction == "FROM":
            out.append([])
        if out:
            out[-1].append((instruction, args))
    return out


def final_cmd() -> list[str]:
    """The last CMD, which must be exec form (a JSON array)."""
    cmds = [a for i, a in stages()[-1] if i == "CMD"]
    assert cmds, "final stage has no CMD"
    value = json.loads(cmds[-1])
    assert isinstance(value, list)
    return [str(v) for v in value]


def compose() -> Doc:
    data: Doc = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    return data
