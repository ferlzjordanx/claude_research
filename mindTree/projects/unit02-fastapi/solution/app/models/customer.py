"""API schemas (DTOs). They are the contract, separate from storage."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CustomerCreate(BaseModel):
    # extra="forbid": unknown fields are a client bug -> 422, not ignored
    model_config = ConfigDict(extra="forbid")

    name: Name
    email: EmailStr
    company: Annotated[str | None, Field(max_length=120)] = None


class CustomerUpdate(BaseModel):
    """PATCH body: every field optional; only sent fields change."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    email: EmailStr | None = None
    company: Annotated[str | None, Field(max_length=120)] = None
    status: CustomerStatus | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> CustomerUpdate:
        # Omitting a field means "leave it"; sending null for a required
        # field is a client error, caught here at the boundary (422).
        for name in ("name", "email", "status"):
            if (
                name in self.model_fields_set
                and getattr(self, name) is None
            ):
                raise ValueError(f"{name} cannot be null")
        return self


class Customer(BaseModel):
    """Internal domain object returned by the repository."""

    id: int
    name: str
    email: str
    company: str | None
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    company: str | None
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime


class CustomerPage(BaseModel):
    items: list[CustomerOut]
    total: int
    limit: int
    offset: int
