"""Idempotency store and charge ledger (in memory, guarded by a lock).

Production version: a table with a UNIQUE idempotency_key column and
`INSERT ... ON CONFLICT DO NOTHING`, so two replicas cannot both
claim the same key. The rules stay exactly the same.
"""

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass
from typing import Any

from common.problems import DomainError


class IdempotencyMismatch(DomainError):
    status_code = 422
    title = "Idempotency key reused"


class IdempotencyInProgress(DomainError):
    status_code = 409
    title = "Request in progress"


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]
    media_type: str = "application/json"


@dataclass
class _Entry:
    fingerprint: str
    response: StoredResponse | None  # None means "still processing"


def fingerprint(body: dict[str, Any]) -> str:
    """Stable hash of the request body (key order does not matter)."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class IdempotencyStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}

    def begin(self, key: str, body_hash: str) -> StoredResponse | None:
        """Claim `key`, or return the response to replay.

        - unknown key        -> claim it, return None (caller processes)
        - same key + body    -> return the stored response (replay)
        - same key, new body -> IdempotencyMismatch (422)
        - claimed, no result -> IdempotencyInProgress (409)
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._entries[key] = _Entry(body_hash, None)
                return None
            if entry.fingerprint != body_hash:
                raise IdempotencyMismatch(
                    "This Idempotency-Key was used with a different "
                    "request body."
                )
            if entry.response is None:
                raise IdempotencyInProgress(
                    "A request with this Idempotency-Key is still "
                    "being processed. Retry later."
                )
            return entry.response

    def complete(self, key: str, response: StoredResponse) -> None:
        with self._lock:
            self._entries[key].response = response

    def abandon(self, key: str) -> None:
        """Release a claim when processing failed with no side effect."""
        with self._lock:
            self._entries.pop(key, None)


@dataclass(frozen=True)
class Charge:
    payment_id: str
    order_id: int
    amount_cents: int
    currency: str


class Ledger:
    """Every successful charge. 'Charged twice' shows up here."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._charges: list[Charge] = []

    def charge(
        self, order_id: int, amount_cents: int, currency: str
    ) -> Charge:
        charge = Charge(
            f"pay_{uuid.uuid4().hex[:12]}", order_id, amount_cents, currency
        )
        with self._lock:
            self._charges.append(charge)
        return charge

    def list(self, order_id: int | None = None) -> list[Charge]:
        with self._lock:
            return [
                c
                for c in self._charges
                if order_id is None or c.order_id == order_id
            ]
