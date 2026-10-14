"""The intake fields agreed in discovery (requirements.md FR-1)."""

from enum import StrEnum


class Field(StrEnum):
    PATIENT_NAME = "patient_name"
    DATE_OF_BIRTH = "date_of_birth"
    PHONE = "phone"
    EMAIL = "email"
    POLICY_NUMBER = "insurance_policy_number"
    REASON = "reason_for_visit"
    PREFERRED_DATE = "preferred_date"


ALL_FIELDS: tuple[Field, ...] = tuple(Field)

# Without these, front-desk staff cannot book the visit (FR-2).
REQUIRED_FIELDS: frozenset[Field] = frozenset(
    {
        Field.PATIENT_NAME,
        Field.DATE_OF_BIRTH,
        Field.PHONE,
        Field.REASON,
    }
)
