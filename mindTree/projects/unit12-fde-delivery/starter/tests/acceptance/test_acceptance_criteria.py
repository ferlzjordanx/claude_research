"""Executable acceptance criteria.

One test per AC in docs/requirements.md section 8, named after its
ID, with the Given/When/Then text as the docstring. If the customer
changes an AC, this file changes in the same pull request.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from tests.conftest import sample


def submit(client: TestClient, name: str) -> dict[str, object]:
    resp = client.post("/intake", json={"text": sample(name)})
    assert resp.status_code == 201, resp.text
    body: dict[str, object] = resp.json()
    return body


def test_ac1_complete_intake_is_auto_accepted(client: TestClient) -> None:
    """AC-1
    Given an intake email with name, DOB, phone and reason clearly
      stated
    When it is submitted
    Then it is auto-accepted, does not appear in the review queue,
      and every field records its source and confidence.
    """
    body = submit(client, "01_clean_email.txt")
    assert body["status"] == "auto_accepted"
    assert client.get("/review-queue").json() == []
    fields = body["fields"]
    assert isinstance(fields, dict)
    assert fields["date_of_birth"]["value"] == "1985-03-14"
    assert all("source" in f and "confidence" in f for f in fields.values())


def test_ac2_missing_required_field_goes_to_review(
    client: TestClient,
) -> None:
    """AC-2
    Given an intake with no date of birth
    When it is submitted
    Then it is placed in the review queue with the reason
      "date_of_birth: required field missing".
    """
    body = submit(client, "03_missing_dob.txt")
    assert body["status"] == "pending_review"
    assert "date_of_birth: required field missing" in body["reasons"]
    queue_ids = [s["id"] for s in client.get("/review-queue").json()]
    assert body["id"] in queue_ids


def test_ac3_extractor_conflict_keeps_deterministic_and_flags(
    client: TestClient,
) -> None:
    """AC-3
    Given an intake where the regex and the LLM find different phone
      numbers
    When it is submitted
    Then the regex value is kept, the LLM value is shown as the
      conflicting value, and the intake goes to review.
    """
    body = submit(client, "04_two_phones.txt")
    phone = body["fields"]["phone"]  # type: ignore[index]
    assert phone["value"] == "+15550102222"
    assert phone["source"] == "deterministic"
    assert phone["conflict_with"] == "+15550103333"
    assert body["status"] == "pending_review"


def test_ac4_low_confidence_goes_to_review(client: TestClient) -> None:
    """AC-4
    Given a messy forwarded email where the name is only guessed from
      the sign-off
    When it is submitted
    Then it goes to review with a confidence reason for that field.
    """
    body = submit(client, "05_messy_forwarded.txt")
    assert body["status"] == "pending_review"
    reasons = body["reasons"]
    assert isinstance(reasons, list)
    assert any(r.startswith("patient_name: confidence") for r in reasons)


def test_ac5_implausible_dob_goes_to_review(client: TestClient) -> None:
    """AC-5
    Given an intake whose date of birth is in the future
    When it is submitted
    Then it is not auto-accepted and the reason names the field.
    """
    body = submit(client, "06_future_dob.txt")
    assert body["status"] == "pending_review"
    assert body["issues"] == {
        "date_of_birth": "date of birth is in the future"
    }


def test_ac6_reviewer_corrections_are_audited(client: TestClient) -> None:
    """AC-6
    Given an intake in the review queue
    When reviewer "desk.jo" approves it with a corrected phone number
    Then the audit log shows desk.jo, the field, the old value and the
      new value, and the intake leaves the queue as approved.
    """
    sid = submit(client, "04_two_phones.txt")["id"]
    resp = client.post(
        f"/review/{sid}/approve",
        json={
            "reviewer": "desk.jo",
            "corrections": {"phone": "+15550103333"},
        },
    )
    assert resp.json()["status"] == "approved"
    audit = client.get(f"/intake/{sid}/audit").json()
    fix = next(a for a in audit if a["action"] == "correct")
    assert (fix["actor"], fix["field"]) == ("desk.jo", "phone")
    assert fix["old_value"] == "+15550102222"
    assert fix["new_value"] == "+15550103333"
    assert client.get("/review-queue").json() == []


def test_ac7_metrics_report_automation_and_corrections(
    client: TestClient,
) -> None:
    """AC-7
    Given two auto-accepted intakes and two reviewed intakes, one of
      which needed a phone correction
    When the sponsor opens the metrics summary
    Then it shows 2 auto-accepted, 2 sent to review, a 50%
      auto-accept rate and a 50% phone correction rate.
    """
    # TODO(4): turn the Given/When/Then above into code:
    #   submit 01 and 02 (auto), submit 04 and 06 (review), approve
    #   04 with a phone correction and 06 with a DOB correction, then
    #   assert on GET /metrics/summary.
    pytest.fail("TODO(4): write the AC-7 acceptance test")


def test_ac8_no_patient_data_in_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-8
    Given an intake containing a name, DOB, phone and email
    When it is submitted and reviewed
    Then no application log line contains any of those values.
    """
    caplog.set_level(logging.DEBUG)
    sid = submit(client, "04_two_phones.txt")["id"]
    client.post(
        f"/review/{sid}/approve",
        json={"reviewer": "r", "corrections": {"phone": "+15550103333"}},
    )
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "intake id=" in logged  # we do log, just not PHI
    for secret in ("Robert", "Chen", "1952", "5550102222", "5550103333"):
        assert secret not in logged
