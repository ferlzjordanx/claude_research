"""Offline eval: run the golden set through the real service.

    python -m evals.run_eval                    # fake provider
    APP_LLM_PROVIDER=anthropic python -m evals.run_eval --threshold 0.8

Exit code 0 = every field meets the threshold and the fallback rate
is within budget; 1 = regression. CI uses the exit code as a gate.
With the fake provider this proves the harness works; it says
nothing about model quality. Run it against a real provider before
changing the prompt, the model or the schema.
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.llm import build_llm
from app.triage import CallPolicy, TriageOutcome, TriageService

GOLDEN = Path(__file__).with_name("golden_set.json")
FIELDS = ("category", "priority", "needs_human")


@dataclass(frozen=True)
class GoldenCase:
    id: str
    text: str
    expected: dict[str, object]


@dataclass
class EvalReport:
    total: int
    accuracy: dict[str, float]
    fallback_rate: float
    cost_usd: float | None
    failures: list[str] = field(default_factory=list)

    def passed(self, threshold: float, max_fallback: float) -> bool:
        return (
            all(v >= threshold for v in self.accuracy.values())
            and self.fallback_rate <= max_fallback
        )


def load_cases(path: Path = GOLDEN) -> list[GoldenCase]:
    cases = []
    for raw in json.loads(path.read_text(encoding="utf-8")):
        text = raw["text"]
        if isinstance(text, list):  # long texts are split for print
            text = " ".join(text)
        expected = {name: raw[name] for name in FIELDS}
        cases.append(GoldenCase(raw["id"], text, expected))
    return cases


def score(
    cases: Sequence[GoldenCase], predictions: Sequence[dict[str, object]]
) -> tuple[dict[str, float], list[str]]:
    """Exact-match accuracy per field, plus one line per mismatch."""
    if len(cases) != len(predictions):
        raise ValueError("cases and predictions differ in length")
    if not cases:
        raise ValueError("empty golden set")
    hits = dict.fromkeys(FIELDS, 0)
    failures: list[str] = []
    for case, pred in zip(cases, predictions, strict=True):
        for name in FIELDS:
            if pred.get(name) == case.expected[name]:
                hits[name] += 1
            else:
                failures.append(
                    f"{case.id} {name}: expected "
                    f"{case.expected[name]!r}, got {pred.get(name)!r}"
                )
    accuracy = {n: round(hits[n] / len(cases), 3) for n in FIELDS}
    return accuracy, failures


async def evaluate(
    service: TriageService, cases: Sequence[GoldenCase]
) -> EvalReport:
    outcomes: list[TriageOutcome] = []
    for case in cases:  # sequential: gentle on rate limits
        outcomes.append(await service.triage(case.text))
    predictions = [o.result.model_dump(mode="json") for o in outcomes]
    accuracy, failures = score(cases, predictions)
    costs = [o.cost_estimate_usd for o in outcomes]
    known = [c for c in costs if c is not None]
    return EvalReport(
        total=len(cases),
        accuracy=accuracy,
        fallback_rate=sum(o.fallback_used for o in outcomes) / len(cases),
        cost_usd=round(sum(known), 6) if known else None,
        failures=failures,
    )


def main(
    argv: Sequence[str] | None = None, settings: Settings | None = None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=GOLDEN)
    parser.add_argument("--threshold", type=float, default=0.75)
    parser.add_argument("--max-fallback", type=float, default=0.1)
    args = parser.parse_args(argv)

    settings = settings or Settings()
    service = TriageService(
        build_llm(settings),
        CallPolicy(
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            confidence_threshold=settings.confidence_threshold,
        ),
        settings.prices,
    )
    report = asyncio.run(evaluate(service, load_cases(args.golden)))

    print(
        f"provider={settings.llm_provider} "
        f"model={settings.active_model} cases={report.total}"
    )
    for name, value in report.accuracy.items():
        print(f"  {name:<12} {value:6.1%}")
    print(f"  fallback     {report.fallback_rate:6.1%}")
    print(f"  cost_usd     {report.cost_usd}")
    for line in report.failures:
        print(f"  MISS {line}")
    ok = report.passed(args.threshold, args.max_fallback)
    print("PASS" if ok else f"FAIL (threshold {args.threshold:.0%})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
