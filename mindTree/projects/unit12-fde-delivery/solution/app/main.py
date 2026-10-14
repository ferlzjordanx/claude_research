"""Application factory and HTTP routes (thin: logic is in service)."""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, get_settings
from app.errors import CorrectionError, DomainError
from app.extraction.llm import FakeExtractor, LLMExtractor
from app.models import AuditEntry, MetricsSummary, Submission
from app.repository import InMemoryRepository
from app.service import IntakeService


class IntakeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=20_000)
    channel: Literal["email", "web_form"] = "email"


class ApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Pilot: the reviewer's name in the body. Production: the
    # identity from the customer's SSO token (Unit 2), never a field
    # the client can set.
    reviewer: str = Field(min_length=1, max_length=100)
    corrections: dict[str, str | None] = {}
    note: str | None = Field(default=None, max_length=500)


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=3, max_length=500)


def build_extractor(settings: Settings) -> LLMExtractor:
    # Plug-in point for the Unit 9 adapters:
    #   if settings.extractor == "anthropic":
    #       return AnthropicExtractor(client, model="claude-opus-5-5")
    return FakeExtractor()


def create_app(
    settings: Settings | None = None,
    extractor: LLMExtractor | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Run with: uvicorn app.main:create_app --factory --reload"""
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_settings()
    service = IntakeService(
        InMemoryRepository(),
        extractor or build_extractor(settings),
        settings,
        clock,
    )

    app = FastAPI(
        title="Intake Automation Kit",
        version="1.0.0",
        description="Unit 12: Northwind Clinics intake pilot.",
    )
    app.state.service = service

    def get_service(request: Request) -> IntakeService:
        svc: IntakeService = request.app.state.service
        return svc

    Svc = Annotated[IntakeService, Depends(get_service)]

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        body: dict[str, object] = {"detail": exc.detail}
        if isinstance(exc, CorrectionError):
            body["issues"] = exc.issues
        return JSONResponse(body, status_code=exc.status_code)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/intake",
        status_code=status.HTTP_201_CREATED,
        tags=["intake"],
    )
    def submit(body: IntakeIn, svc: Svc) -> Submission:
        return svc.submit(body.text, body.channel)

    @app.get("/intake/{submission_id}", tags=["intake"])
    def get_one(submission_id: int, svc: Svc) -> Submission:
        return svc.get(submission_id)

    @app.get("/intake/{submission_id}/audit", tags=["review"])
    def audit(submission_id: int, svc: Svc) -> list[AuditEntry]:
        return svc.audit_for(submission_id)

    @app.get("/review-queue", tags=["review"])
    def review_queue(svc: Svc) -> list[Submission]:
        return svc.review_queue()

    @app.post("/review/{submission_id}/approve", tags=["review"])
    def approve(
        submission_id: int, body: ApproveIn, svc: Svc
    ) -> Submission:
        return svc.approve(
            submission_id, body.reviewer, body.corrections, body.note
        )

    @app.post("/review/{submission_id}/reject", tags=["review"])
    def reject(submission_id: int, body: RejectIn, svc: Svc) -> Submission:
        return svc.reject(submission_id, body.reviewer, body.reason)

    @app.get("/metrics/summary", tags=["metrics"])
    def metrics(svc: Svc) -> MetricsSummary:
        return svc.metrics()

    return app
