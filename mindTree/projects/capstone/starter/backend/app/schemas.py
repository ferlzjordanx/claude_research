"""API contract shared with the SPA (src/api/types.ts mirrors it)."""

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


class Category(StrEnum):
    DELIVERY = "delivery"
    BILLING = "billing"
    DAMAGE = "damage"
    ACCOUNT = "account"
    OTHER = "other"


class TriageResult(BaseModel):
    """What the model must return. Validated; never trusted blindly."""

    category: Category
    priority: Priority
    summary: Annotated[str, Field(min_length=1, max_length=200)]
    confidence: Annotated[float, Field(ge=0, le=1)]


class AiTriageOut(BaseModel):
    status: str  # pending | done | fallback
    category: Category | None = None
    priority: Priority | None = None
    summary: str | None = None
    confidence: float | None = None
    needs_human: bool = True


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    priority: Priority
    status: TicketStatus
    owner: str
    created_at: datetime
    ai: AiTriageOut | None = None


class ReplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: Annotated[str, Field(min_length=1, max_length=4000)]


class ReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticket_id: int
    body: str
    citations: list[str]
    status: str
    ai_generated: bool
    created_by: str
    approved_by: str | None
    created_at: datetime


class DraftOut(BaseModel):
    reply: ReplyOut
    stop_reason: str
    tool_calls: list[str]


class TicketPage(BaseModel):
    items: list[TicketOut]
    total: int
