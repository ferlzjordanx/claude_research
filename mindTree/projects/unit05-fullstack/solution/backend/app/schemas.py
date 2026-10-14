"""The API contract shared with the SPA (src/api/types.ts mirrors it)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Role(StrEnum):
    REQUESTER = "requester"
    AGENT = "agent"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class User(BaseModel):
    username: str
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=3, max_length=120
        ),
    ]
    description: Annotated[str, Field(max_length=2000)] = ""
    priority: Priority = Priority.MEDIUM


class TicketStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TicketStatus


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    priority: Priority
    status: TicketStatus
    owner: str
    created_at: datetime


class TicketPage(BaseModel):
    items: list[TicketOut]
    total: int
