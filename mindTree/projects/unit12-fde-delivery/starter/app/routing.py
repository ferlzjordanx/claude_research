"""Routing: auto-accept or send to the human review queue.

The rule is deliberately conservative for a healthcare pilot: when
in doubt, a person looks at it. Precision first; automation rate is
tuned later with real correction data (requirements.md NFR-3).
"""

from collections.abc import Mapping

from app.fields import REQUIRED_FIELDS, Field  # noqa: F401
from app.models import (  # noqa: F401
    FieldResult,
    Route,
    RouteDecision,
)


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
    # TODO(2): build ``reasons`` (one string per problem):
    #   - "<field>: <problem>" for each validation issue (sorted);
    #   - "<field>: extractors disagree (kept deterministic)" for
    #     each field with conflict_with set;
    #   - "<field>: confidence 0.60 < 0.85" for each REQUIRED field
    #     that has a value but confidence < threshold (2 decimals).
    # Route.REVIEW if there is any reason, else Route.AUTO_ACCEPT.
    raise NotImplementedError("TODO(2)")
