"""Data shapes shared by the pipeline, the service and the API."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Source(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HUMAN = "human"
    NONE = "none"


class Route(StrEnum):
    AUTO_ACCEPT = "auto_accept"
    REVIEW = "review"


class Status(StrEnum):
    AUTO_ACCEPTED = "auto_accepted"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Candidate(BaseModel):
    """One extractor's answer for one field."""

    model_config = ConfigDict(frozen=True)

    value: str
    confidence: float = Field(ge=0.0, le=1.0)


class FieldResult(BaseModel):
    """The merged answer for one field, with its provenance."""

    value: str | None
    source: Source
    confidence: float = Field(ge=0.0, le=1.0)
    # The value the losing extractor proposed, when they disagreed.
    conflict_with: str | None = None


class RouteDecision(BaseModel):
    route: Route
    reasons: list[str]


class Submission(BaseModel):
    id: int
    received_at: datetime
    channel: str
    raw_text: str
    fields: dict[str, FieldResult]
    issues: dict[str, str]
    route: Route
    reasons: list[str]
    status: Status
    reviewed_by: str | None = None
    corrected_fields: list[str] = []

    def values(self) -> dict[str, str | None]:
        return {name: f.value for name, f in self.fields.items()}


class AuditEntry(BaseModel):
    """Who changed what, and when. Append-only."""

    model_config = ConfigDict(frozen=True)

    submission_id: int
    at: datetime
    actor: str
    action: str  # auto_accept | route_review | correct | approve | reject
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    note: str | None = None


class MetricsSummary(BaseModel):
    total: int
    auto_accepted: int
    sent_to_review: int
    pending_review: int
    approved: int
    rejected: int
    auto_accept_rate: float
    corrections_total: int
    # corrected approvals / approved reviews, per field. The pilot's
    # business metric: how often humans still fix each field.
    field_correction_rates: dict[str, float]
