"""Merge deterministic and LLM candidates with precedence rules.

Precedence (ADR-0001):
1. Deterministic wins on conflict: a regex is auditable and tested.
2. A disagreement is never silent: the loser's value is kept in
   ``conflict_with`` so routing sends it to a human.
3. LLM fills only the gaps the deterministic pass left.
4. Nothing found -> value None, source NONE, confidence 0.
"""

from collections.abc import Mapping, Sequence

from app.fields import Field
from app.models import Candidate, FieldResult, Source  # noqa: F401


def same_value(a: str, b: str) -> bool:
    """Case and whitespace do not count as a disagreement."""
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def merge(
    deterministic: Mapping[Field, Candidate],
    llm: Mapping[Field, Candidate],
    fields: Sequence[Field],
) -> dict[Field, FieldResult]:
    # TODO(1): for each field in ``fields``:
    #   - deterministic present -> use it (source DETERMINISTIC);
    #     if the LLM also answered with a different value
    #     (not same_value), put the LLM value in conflict_with;
    #   - only the LLM answered -> use it (source LLM, its confidence);
    #   - nobody answered -> value None, source NONE, confidence 0.0.
    # Return one FieldResult for every field in ``fields``.
    raise NotImplementedError("TODO(1)")
