"""Payments service: POST /payments is safe to retry.

Run: uvicorn payments.main:create_app --factory --port 8001
"""

import asyncio
import logging
import re
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from common.problems import (
    PROBLEM_JSON,
    DomainError,
    register_error_handlers,
)
from payments.config import PaymentsSettings, get_payments_settings
from payments.faults import FaultInjector, FaultMode, Sleep
from payments.store import (
    IdempotencyStore,
    Ledger,
    StoredResponse,
    fingerprint,
)

log = logging.getLogger("payments")
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


class PaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int = Field(gt=0)
    amount_cents: int = Field(gt=0, le=10_000_000)
    currency: Literal["USD", "EUR"] = "USD"


class BadIdempotencyKey(DomainError):
    status_code = 400
    title = "Idempotency-Key required"


def create_app(
    settings: PaymentsSettings | None = None,
    *,
    sleep: Sleep | None = None,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_payments_settings()
    app = FastAPI(title="Payments", version="1.0.0")
    register_error_handlers(app)

    # Built here, not in a lifespan, so tests that mount the app with
    # httpx.ASGITransport (which skips lifespan) still get them.
    store = IdempotencyStore()
    ledger = Ledger()
    faults = FaultInjector(
        settings.fault_error_rate,
        settings.fault_latency_ms,
        sleep=sleep or asyncio.sleep,
    )
    app.state.store, app.state.ledger = store, ledger
    app.state.faults = faults
    header_faults = settings.fault_header_enabled and settings.env != "prod"

    @app.post("/payments", status_code=201)
    async def create_payment(
        body: PaymentRequest,
        idempotency_key: Annotated[str | None, Header()] = None,
        x_fault: Annotated[FaultMode | None, Header()] = None,
    ) -> JSONResponse:
        if idempotency_key is None or not KEY_PATTERN.match(
            idempotency_key
        ):
            raise BadIdempotencyKey(
                "Send an Idempotency-Key header (8-128 chars of "
                "A-Z a-z 0-9 _ -)."
            )
        mode = x_fault if header_faults else None
        # Outage-style faults happen before we claim the key, like a
        # gateway failing in front of the service.
        await faults.before_charge(mode)

        replay = store.begin(
            idempotency_key, fingerprint(body.model_dump())
        )
        if replay is not None:
            log.info("replay key=%s", idempotency_key)
            return _respond(replay, replayed=True)
        try:
            stored = _process(body, settings, ledger)
        except Exception:
            store.abandon(idempotency_key)  # nothing was charged
            raise
        store.complete(idempotency_key, stored)
        log.info(
            "key=%s order=%s -> %s",
            idempotency_key,
            body.order_id,
            stored.status_code,
        )
        faults.after_charge(mode)  # charged, then "crash"
        return _respond(stored, replayed=False)

    @app.get("/payments")
    async def list_payments(
        order_id: int | None = None,
    ) -> list[dict[str, object]]:
        return [asdict(c) for c in ledger.list(order_id)]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _process(
    body: PaymentRequest, settings: PaymentsSettings, ledger: Ledger
) -> StoredResponse:
    if body.amount_cents > settings.decline_over_cents:
        # A decline is a final answer: stored and replayed like success.
        return StoredResponse(
            402,
            {
                "type": "about:blank",
                "title": "Payment declined",
                "status": 402,
                "detail": "The card issuer declined the charge.",
            },
            PROBLEM_JSON,
        )
    charge = ledger.charge(body.order_id, body.amount_cents, body.currency)
    return StoredResponse(201, {**asdict(charge), "status": "captured"})


def _respond(stored: StoredResponse, *, replayed: bool) -> JSONResponse:
    headers = {"Idempotent-Replayed": "true"} if replayed else {}
    return JSONResponse(
        stored.body,
        stored.status_code,
        headers=headers,
        media_type=stored.media_type,
    )
