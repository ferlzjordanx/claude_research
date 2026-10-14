from app.fields import ALL_FIELDS, Field
from app.merge import merge
from app.models import Candidate, Source

DET = Candidate(value="+15550102222", confidence=1.0)


def test_deterministic_wins_and_conflict_is_flagged() -> None:
    llm = {Field.PHONE: Candidate(value="+15550103333", confidence=0.9)}
    out = merge({Field.PHONE: DET}, llm, ALL_FIELDS)
    assert out[Field.PHONE].value == "+15550102222"
    assert out[Field.PHONE].source is Source.DETERMINISTIC
    assert out[Field.PHONE].conflict_with == "+15550103333"


def test_agreement_is_not_a_conflict() -> None:
    det = {Field.EMAIL: Candidate(value="a@example.com", confidence=1)}
    llm = {Field.EMAIL: Candidate(value=" A@Example.com", confidence=1)}
    out = merge(det, llm, ALL_FIELDS)
    assert out[Field.EMAIL].conflict_with is None


def test_llm_fills_gaps_with_its_own_confidence() -> None:
    llm = {Field.REASON: Candidate(value="back pain", confidence=0.7)}
    out = merge({}, llm, ALL_FIELDS)
    assert out[Field.REASON].source is Source.LLM
    assert out[Field.REASON].confidence == 0.7


def test_missing_everywhere_is_explicit_none() -> None:
    out = merge({}, {}, ALL_FIELDS)
    assert set(out) == set(ALL_FIELDS)
    assert out[Field.EMAIL].value is None
    assert out[Field.EMAIL].source is Source.NONE
    assert out[Field.EMAIL].confidence == 0.0
