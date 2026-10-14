"""Routing: auto-accept or send to the human review queue.

The rule is deliberately conservative for a healthcare pilot: when
in doubt, a person looks at it. Precision first; automation rate is
tuned later with real correction data (requirements.md NFR-3).
"""

from collections.abc import Mapping

from app.fields import REQUIRED_FIELDS, Field
from app.models import FieldResult, Route, RouteDecision


def decide_route(
    merged: Mapping[Field, FieldResult],
    issues: Mapping[str, str],
    threshold: float,
) -> RouteDecision:
    """Auto-accept only if all of these hold:

    - no validation issues (required present, formats, dates);
    - no extractor conflicts on any field;
    - every required field has confidence >= threshold.

    Reasons name fields, never values (no PHI in logs or metrics).
    """
    reasons: list[str] = [
        f"{name}: {problem}" for name, problem in sorted(issues.items())
    ]
    for field in sorted(merged):
        result = merged[field]
        if result.conflict_with is not None:
            reasons.append(
                f"{field}: extractors disagree (kept deterministic)"
            )
        if (
            field in REQUIRED_FIELDS
            and result.value is not None
            and result.confidence < threshold
        ):
            reasons.append(
                f"{field}: confidence {result.confidence:.2f}"
                f" < {threshold:.2f}"
            )
    route = Route.REVIEW if reasons else Route.AUTO_ACCEPT
    return RouteDecision(route=route, reasons=reasons)
