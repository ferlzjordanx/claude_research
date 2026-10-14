import json
from pathlib import Path

import pytest

from evals.retrieval_eval import main


def test_eval_passes_with_default_thresholds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "recall@3=" in out and "PASS" in out


def test_eval_fails_when_threshold_is_not_met() -> None:
    assert main(["--min-recall", "0.99"]) == 1


def test_eval_fails_when_role_cannot_reach_the_answer(
    tmp_path: Path,
) -> None:
    cases = [
        {
            "q": "fraud flag",
            "role": "customer",
            "expected": ["escalation-playbook"],
        }
    ]
    kb = tmp_path / "kb"
    kb.mkdir()
    # The only relevant doc is internal: a customer case must miss.
    (kb / "a.md").write_text(
        "---\nid: escalation-playbook\ntitle: E\naudience: internal\n"
        "---\n# E\n\n## Fraud\n\nFraud flag goes to risk.\n"
    )
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases))
    assert main(["--cases", str(path), "--kb", str(kb)]) == 1
