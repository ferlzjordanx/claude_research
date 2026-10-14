"""HTTP endpoints. Thin: parse input, call services, shape output."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_session
from app.fx import FxClient
from app.legacy import render_report
from app.schemas import FxReport, RevenueRow
from app.services import ReportService

router = APIRouter()


def get_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> ReportService:
    return ReportService(session, request.app.state.tracer)


def get_fx(request: Request) -> FxClient:
    fx: FxClient = request.app.state.fx
    return fx


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


Service = Annotated[ReportService, Depends(get_service)]


# Plain `def`: FastAPI runs it in a worker thread, so the blocking
# SQLAlchemy call does not stall the event loop.
@router.get("/customers/{customer_id}/summary")
def customer_summary(customer_id: int, service: Service) -> RevenueRow:
    return service.customer_summary(customer_id)


@router.get("/reports/revenue")
def revenue(service: Service) -> list[RevenueRow]:
    return service.revenue_by_customer()


@router.get("/reports/revenue-fx")
async def revenue_fx(
    service: Service,
    fx: Annotated[FxClient, Depends(get_fx)],
    currency: Annotated[str, Query(pattern="^[A-Z]{3}$")] = "EUR",
) -> FxReport:
    # The SQLite query takes ~1 ms; a slow DB here would need an async
    # driver or a thread, exactly like the renderer below.
    total = sum(r.total_cents for r in service.revenue_by_customer())
    rate = await fx.get_rate(currency)
    return FxReport(
        currency=currency,
        rate=rate,
        total_cents_usd=total,
        total_cents_converted=round(total * rate),
    )


@router.get("/reports/export")
async def export(
    service: Service,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Response:
    rows = service.revenue_by_customer()
    # Blocking code inside `async def` freezes every request on this
    # worker. Run it in a thread and await the result.
    body = await asyncio.to_thread(
        render_report, rows, settings.render_delay_seconds
    )
    return Response(body, media_type="text/csv")
