import pytest

from app.config import Settings
from app.errors import CorrectionError, NotFoundError, StateError
from app.fields import Field
from app.models import Candidate, Source, Status
from app.repository import InMemoryRepository
from app.service import IntakeService
from tests.conftest import FROZEN_NOW, StubExtractor, sample


def test_correction_writes_one_audit_entry_per_changed_field(
    service: IntakeService,
) -> None:
    sub = service.submit(sample("04_two_phones.txt"), "email")
    service.approve(
        sub.id,
        "desk.jo",
        {
            "phone": "+15550103333",
            "patient_name": "Robert Chen",  # unchanged: not a fix
        },
    )
    entries = service.audit_for(sub.id)
    actions = [e.action for e in entries]
    assert actions == ["route_review", "correct", "approve"]
    fix = entries[1]
    assert fix.actor == "desk.jo"
    assert fix.field == "phone"
    assert fix.old_value == "+15550102222"
    assert fix.new_value == "+15550103333"
    assert fix.at == FROZEN_NOW


def test_corrected_field_becomes_human_sourced(
    service: IntakeService,
) -> None:
    sub = service.submit(sample("04_two_phones.txt"), "email")
    out = service.approve(sub.id, "desk.jo", {"phone": "+15550103333"})
    assert out.fields["phone"].source is Source.HUMAN
    assert out.corrected_fields == ["phone"]
    assert out.status is Status.APPROVED
    assert out.reviewed_by == "desk.jo"


def test_invalid_correction_is_refused_and_not_audited(
    service: IntakeService,
) -> None:
    sub = service.submit(sample("06_future_dob.txt"), "email")
    with pytest.raises(CorrectionError) as exc:
        service.approve(sub.id, "desk.jo", {"date_of_birth": "2063-01-01"})
    assert "date_of_birth" in exc.value.issues
    assert [e.action for e in service.audit_for(sub.id)] == ["route_review"]


def test_cannot_review_twice_or_review_auto_accepted(
    service: IntakeService,
) -> None:
    auto = service.submit(sample("01_clean_email.txt"), "email")
    with pytest.raises(StateError):
        service.approve(auto.id, "desk.jo", {})
    queued = service.submit(sample("06_future_dob.txt"), "email")
    service.reject(queued.id, "desk.jo", "duplicate")
    with pytest.raises(StateError):
        service.reject(queued.id, "desk.jo", "again")


def test_unknown_submission_and_unknown_field(
    service: IntakeService,
) -> None:
    with pytest.raises(NotFoundError):
        service.get(999)
    sub = service.submit(sample("03_missing_dob.txt"), "email")
    with pytest.raises(CorrectionError) as exc:
        service.approve(sub.id, "desk.jo", {"ssn": "123"})
    assert exc.value.issues == {"ssn": "unknown field"}


def test_cross_check_off_only_asks_llm_for_gaps() -> None:
    stub = StubExtractor(
        {Field.PHONE: Candidate(value="+15550103333", confidence=0.9)}
    )
    svc = IntakeService(
        InMemoryRepository(),
        stub,
        Settings(env="test", llm_cross_check=False),
        clock=lambda: FROZEN_NOW,
    )
    sub = svc.submit(sample("04_two_phones.txt"), "email")
    assert Field.PHONE not in stub.asked[0]
    assert sub.fields["phone"].conflict_with is None
