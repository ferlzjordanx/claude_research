"""Payments: Idempotency-Key makes POST /payments safe to retry."""

import httpx
import pytest
from fastapi import FastAPI

from payments.store import (
    IdempotencyInProgress,
    IdempotencyStore,
    fingerprint,
)

BODY = {"order_id": 7, "amount_cents": 2500, "currency": "USD"}
KEY = {"Idempotency-Key": "order-abc12345"}


async def test_first_request_charges_once(
    payments_client: httpx.AsyncClient, payments_app: FastAPI
) -> None:
    response = await payments_client.post(
        "/payments", json=BODY, headers=KEY
    )
    assert response.status_code == 201
    assert response.json()["status"] == "captured"
    assert "Idempotent-Replayed" not in response.headers
    assert len(payments_app.state.ledger.list(order_id=7)) == 1


async def test_same_key_same_body_replays_without_new_charge(
    payments_client: httpx.AsyncClient, payments_app: FastAPI
) -> None:
    first = await payments_client.post("/payments", json=BODY, headers=KEY)
    # Same body with keys in another order: same fingerprint.
    reordered = dict(reversed(list(BODY.items())))
    second = await payments_client.post(
        "/payments", json=reordered, headers=KEY
    )
    assert second.status_code == first.status_code == 201
    assert second.json() == first.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    charges = await payments_client.get("/payments?order_id=7")
    assert len(charges.json()) == 1


async def test_same_key_different_body_is_rejected(
    payments_client: httpx.AsyncClient,
) -> None:
    await payments_client.post("/payments", json=BODY, headers=KEY)
    other = {**BODY, "amount_cents": 9999}
    response = await payments_client.post(
        "/payments", json=other, headers=KEY
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["title"] == "Idempotency key reused"


@pytest.mark.parametrize("headers", [{}, {"Idempotency-Key": "short"}])
async def test_missing_or_bad_key_is_400(
    payments_client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await payments_client.post(
        "/payments", json=BODY, headers=headers
    )
    assert response.status_code == 400


async def test_decline_is_final_and_replayed(
    payments_client: httpx.AsyncClient, payments_app: FastAPI
) -> None:
    big = {**BODY, "amount_cents": 500_000}
    first = await payments_client.post("/payments", json=big, headers=KEY)
    again = await payments_client.post("/payments", json=big, headers=KEY)
    assert first.status_code == again.status_code == 402
    assert again.headers["Idempotent-Replayed"] == "true"
    assert payments_app.state.ledger.list() == []


async def test_injected_outage_charges_nothing_and_frees_key(
    payments_client: httpx.AsyncClient, payments_app: FastAPI
) -> None:
    down = await payments_client.post(
        "/payments", json=BODY, headers={**KEY, "X-Fault": "error"}
    )
    assert down.status_code == 503
    assert payments_app.state.ledger.list() == []
    retry = await payments_client.post("/payments", json=BODY, headers=KEY)
    assert retry.status_code == 201  # the key was never claimed


async def test_throttle_sends_retry_after(
    payments_client: httpx.AsyncClient,
) -> None:
    response = await payments_client.post(
        "/payments", json=BODY, headers={**KEY, "X-Fault": "throttle"}
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"


def test_concurrent_claim_of_same_key_is_409() -> None:
    store = IdempotencyStore()
    digest = fingerprint(BODY)
    assert store.begin("order-abc12345", digest) is None  # claimed
    with pytest.raises(IdempotencyInProgress):
        store.begin("order-abc12345", digest)
