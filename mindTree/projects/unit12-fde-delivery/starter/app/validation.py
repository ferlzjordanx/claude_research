"""Validation of the merged values (formats, required, date sanity).

Validation runs on *every* path: extracted values, and the values a
reviewer types in. A human can make typos too.
"""

from collections.abc import Mapping
from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from pydantic import Field as PydField

MAX_AGE_YEARS = 120


class IntakeForm(BaseModel):
    """What a valid, bookable intake looks like (FR-2, FR-3)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    patient_name: str = PydField(min_length=2, max_length=100)
    date_of_birth: date
    phone: str = PydField(pattern=r"^\+1\d{10}$")
    reason_for_visit: str = PydField(min_length=3, max_length=500)
    email: str | None = PydField(
        default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    insurance_policy_number: str | None = PydField(
        default=None, pattern=r"^[A-Z]{3}-\d{7}$"
    )
    preferred_date: date | None = None

    @field_validator("date_of_birth")
    @classmethod
    def dob_is_plausible(cls, v: date, info: ValidationInfo) -> date:
        today = _today(info)
        if v > today:
            raise ValueError("date of birth is in the future")
        if today.year - v.year > MAX_AGE_YEARS:
            raise ValueError("date of birth is more than 120 years ago")
        return v

    @field_validator("preferred_date")
    @classmethod
    def preferred_not_past(
        cls, v: date | None, info: ValidationInfo
    ) -> date | None:
        if v is not None and v < _today(info):
            raise ValueError("preferred date is in the past")
        return v


def _today(info: ValidationInfo) -> date:
    ctx = info.context or {}
    today = ctx.get("today")
    return today if isinstance(today, date) else date.today()


def validate_values(
    values: Mapping[str, str | None], today: date
) -> dict[str, str]:
    """Return {field: problem}. Empty dict means valid."""
    data = {k: v for k, v in values.items() if v is not None}
    try:
        IntakeForm.model_validate(data, context={"today": today})
    except ValidationError as exc:
        issues: dict[str, str] = {}
        for err in exc.errors():
            name = str(err["loc"][0]) if err["loc"] else "_form"
            msg = (
                "required field missing"
                if err["type"] == "missing"
                else err["msg"].removeprefix("Value error, ")
            )
            issues.setdefault(name, msg)
        return issues
    return {}
