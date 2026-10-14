from datetime import date

from app.validation import validate_values

TODAY = date(2026, 10, 14)
GOOD = {
    "patient_name": "Maria Lopez",
    "date_of_birth": "1985-03-14",
    "phone": "+15550101111",
    "reason_for_visit": "annual physical",
    "email": None,
    "insurance_policy_number": "NWH-1234567",
    "preferred_date": "2026-10-20",
}


def test_valid_intake_has_no_issues() -> None:
    assert validate_values(GOOD, TODAY) == {}


def test_missing_required_field_is_named() -> None:
    issues = validate_values({**GOOD, "phone": None}, TODAY)
    assert issues == {"phone": "required field missing"}


def test_future_and_ancient_dob_rejected() -> None:
    future = validate_values({**GOOD, "date_of_birth": "2062-11-02"}, TODAY)
    old = validate_values({**GOOD, "date_of_birth": "1890-01-01"}, TODAY)
    assert "future" in future["date_of_birth"]
    assert "120 years" in old["date_of_birth"]


def test_preferred_date_in_past_rejected() -> None:
    issues = validate_values(
        {**GOOD, "preferred_date": "2026-10-01"}, TODAY
    )
    assert "past" in issues["preferred_date"]


def test_bad_formats_rejected() -> None:
    issues = validate_values(
        {
            **GOOD,
            "phone": "555-1234",
            "email": "not-an-email",
            "insurance_policy_number": "12345",
        },
        TODAY,
    )
    assert set(issues) == {"phone", "email", "insurance_policy_number"}
