"""Domain models. Frozen dataclasses are immutable and hashable."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Quote:
    """A supplier's price for one SKU."""

    sku: str
    supplier: str
    unit_price: Decimal
    available: int

    def __post_init__(self) -> None:
        # Invariants are enforced at construction time, so every Quote
        # that exists in the program is valid.
        if self.unit_price <= 0:
            raise ValueError("unit_price must be positive")
        if self.available < 0:
            raise ValueError("available must be >= 0")


@dataclass(frozen=True, slots=True)
class SupplierFailure:
    """Records why a supplier could not quote a SKU."""

    sku: str
    supplier: str
    reason: str
