from app.fields import ALL_FIELDS, Field
from app.models import FieldResult, Route, Source
from app.routing import decide_route


def results(**overrides: FieldResult) -> dict[Field, FieldResult]:
    base = {
        f: FieldResult(
            value="x", source=Source.DETERMINISTIC, confidence=1.0
        )
        for f in ALL_FIELDS
    }
    base.update({Field(k): v for k, v in overrides.items()})
    return base


def test_all_good_is_auto_accepted() -> None:
    decision = decide_route(results(), {}, 0.85)
    assert decision.route is Route.AUTO_ACCEPT
    assert decision.reasons == []


def test_validation_issue_goes_to_review() -> None:
    decision = decide_route(
        results(), {"phone": "required field missing"}, 0.85
    )
    assert decision.route is Route.REVIEW
    assert decision.reasons == ["phone: required field missing"]


def test_low_confidence_required_field_goes_to_review() -> None:
    low = FieldResult(value="Ana", source=Source.LLM, confidence=0.6)
    decision = decide_route(results(patient_name=low), {}, 0.85)
    assert decision.route is Route.REVIEW
    assert "patient_name: confidence 0.60 < 0.85" in decision.reasons


def test_low_confidence_optional_field_does_not_block() -> None:
    low = FieldResult(value="a@b.co", source=Source.LLM, confidence=0.5)
    decision = decide_route(results(email=low), {}, 0.85)
    assert decision.route is Route.AUTO_ACCEPT


def test_any_conflict_goes_to_review() -> None:
    clash = FieldResult(
        value="NWH-1234567",
        source=Source.DETERMINISTIC,
        confidence=1.0,
        conflict_with="NWH-7654321",
    )
    decision = decide_route(
        results(insurance_policy_number=clash), {}, 0.85
    )
    assert decision.route is Route.REVIEW


def test_threshold_is_inclusive() -> None:
    edge = FieldResult(value="Ana", source=Source.LLM, confidence=0.85)
    decision = decide_route(results(patient_name=edge), {}, 0.85)
    assert decision.route is Route.AUTO_ACCEPT
