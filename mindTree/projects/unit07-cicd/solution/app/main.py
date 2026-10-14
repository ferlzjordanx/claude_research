"""Application factory: wiring only, no business logic."""

from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query

from app.config import Settings, get_settings
from app.pricing import PricingError, line_total


def create_app(settings: Settings | None = None) -> FastAPI:
    """Run with: uvicorn app.main:create_app --factory --reload"""
    settings = settings or get_settings()
    app = FastAPI(title="Pricing API", version=settings.version)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        # Liveness only: cheap, no dependencies. The smoke test and
        # the Kubernetes probes both call it.
        return {"status": "ok"}

    @app.get("/version", tags=["ops"])
    async def version() -> dict[str, str]:
        # The deploy pipeline compares git_sha with the commit it just
        # shipped, so "is my change live?" is a fact, not a guess.
        return {
            "version": settings.version,
            "git_sha": settings.git_sha,
            "env": settings.env,
        }

    @app.get("/quote", tags=["pricing"])
    async def quote(
        unit_price: Annotated[Decimal, Query(ge=0, max_digits=10)],
        quantity: Annotated[int, Query(ge=1, le=100_000)],
    ) -> dict[str, str]:
        try:
            total = line_total(unit_price, quantity)
        except PricingError as exc:  # pragma: no cover - guarded above
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"total": str(total), "currency": "USD"}

    return app
