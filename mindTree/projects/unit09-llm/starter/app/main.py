"""Application factory: wiring only, no business logic."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, get_settings
from app.llm import build_llm
from app.llm.base import LLMClient
from app.triage import CallPolicy, TriageResult, TriageService

MAX_TICKET_CHARS = 8000


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Bounded input = bounded tokens = bounded cost and latency.
    text: str = Field(min_length=1, max_length=MAX_TICKET_CHARS)


class TriageMeta(BaseModel):
    prompt_version: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_estimate_usd: float | None
    fallback_used: bool
    attempts: int
    latency_ms: float
    rules_applied: list[str]


class TriageResponse(BaseModel):
    result: TriageResult
    meta: TriageMeta


def get_service(request: Request) -> TriageService:
    service: TriageService = request.app.state.triage_service
    return service


def create_app(
    settings: Settings | None = None, llm: LLMClient | None = None
) -> FastAPI:
    """Run with: uvicorn app.main:create_app --factory --reload"""
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One long-lived SDK client per process (connection pooling).
        policy = CallPolicy(
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            backoff_base_s=settings.llm_backoff_base_s,
            max_output_tokens=settings.max_output_tokens,
            confidence_threshold=settings.confidence_threshold,
        )
        app.state.triage_service = TriageService(
            llm or build_llm(settings), policy, settings.prices
        )
        yield

    app = FastAPI(
        title="Ticket Triage Service",
        version="1.0.0",
        lifespan=lifespan,
        description="Unit 9 project: LLM-backed ticket triage.",
    )

    Service = Annotated[TriageService, Depends(get_service)]

    @app.post("/triage", response_model=TriageResponse, tags=["triage"])
    async def triage(
        body: TriageRequest, service: Service
    ) -> TriageResponse:
        outcome = await service.triage(body.text)
        return TriageResponse(
            result=outcome.result,
            meta=TriageMeta(
                prompt_version=outcome.prompt_version,
                model=outcome.model,
                input_tokens=outcome.usage.input_tokens,
                output_tokens=outcome.usage.output_tokens,
                cost_estimate_usd=outcome.cost_estimate_usd,
                fallback_used=outcome.fallback_used,
                attempts=outcome.attempts,
                latency_ms=outcome.latency_ms,
                rules_applied=outcome.rules_applied,
            ),
        )

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        # Report the provider, never the key.
        return {"status": "ok", "provider": settings.llm_provider}

    return app
