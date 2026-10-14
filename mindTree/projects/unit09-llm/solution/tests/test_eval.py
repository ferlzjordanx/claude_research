import json
from pathlib import Path

import pytest

from app.config import Settings
from evals.run_eval import FIELDS, GoldenCase, load_cases, main, score


def case(cid: str, **expected: object) -> GoldenCase:
    return GoldenCase(cid, "text", expected)


def test_golden_set_is_well_formed() -> None:
    cases = load_cases()
    assert len(cases) >= 12
    assert len({c.id for c in cases}) == len(cases)
    for c in cases:
        assert set(c.expected) == set(FIELDS)


def test_score_per_field_accuracy() -> None:
    cases = [
        case("a", category="billing", priority="low", needs_human=False),
        case("b", category="account", priority="high", needs_human=True),
    ]
    preds: list[dict[str, object]] = [
        {"category": "billing", "priority": "low", "needs_human": False},
        {"category": "billing", "priority": "high", "needs_human": True},
    ]
    accuracy, failures = score(cases, preds)

    assert accuracy == {
        "category": 0.5,
        "priority": 1.0,
        "needs_human": 1.0,
    }
    assert failures == ["b category: expected 'account', got 'billing'"]


def test_score_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        score([case("a", category="x", priority="y", needs_human=1)], [])


def test_eval_passes_with_fake_provider(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([], settings=settings) == 0
    assert "PASS" in capsys.readouterr().out


def test_eval_fails_below_threshold(
    settings: Settings, tmp_path: Path
) -> None:
    golden = tmp_path / "golden.json"
    golden.write_text(
        json.dumps(
            [
                {
                    "id": "x1",
                    "text": "Charged twice for October.",
                    "category": "account",
                    "priority": "urgent",
                    "needs_human": True,
                }
            ]
        )
    )
    code = main(["--golden", str(golden)], settings=settings)
    assert code == 1
