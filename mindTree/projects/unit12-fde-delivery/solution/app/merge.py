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
from app.models import Candidate, FieldResult, Source


def same_value(a: str, b: str) -> bool:
    """Case and whitespace do not count as a disagreement."""
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def merge(
    deterministic: Mapping[Field, Candidate],
    llm: Mapping[Field, Candidate],
    fields: Sequence[Field],
) -> dict[Field, FieldResult]:
    merged: dict[Field, FieldResult] = {}
    for field in fields:
        det = deterministic.get(field)
        guess = llm.get(field)
        if det is not None:
            conflict = (
                guess.value
                if guess is not None
                and not same_value(det.value, guess.value)
                else None
            )
            merged[field] = FieldResult(
                value=det.value,
                source=Source.DETERMINISTIC,
                confidence=det.confidence,
                conflict_with=conflict,
            )
        elif guess is not None:
            merged[field] = FieldResult(
                value=guess.value,
                source=Source.LLM,
                confidence=guess.confidence,
            )
        else:
            merged[field] = FieldResult(
                value=None, source=Source.NONE, confidence=0.0
            )
    return merged
