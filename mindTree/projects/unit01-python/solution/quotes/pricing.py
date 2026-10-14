"""Pricing rules composed into a calculator (composition > inheritance)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

CENT = Decimal("0.01")


class PricingRule(Protocol):
    def apply(self, subtotal: Decimal, quantity: int) -> Decimal: ...


@dataclass(frozen=True)
class BulkDiscount:
    """Percentage off when quantity reaches a threshold."""

    min_quantity: int
    percent: Decimal

    def apply(self, subtotal: Decimal, quantity: int) -> Decimal:
        if quantity >= self.min_quantity:
            return subtotal * (1 - self.percent / 100)
        return subtotal


@dataclass(frozen=True)
class FlatShipping:
    """Adds a fixed shipping fee below a free-shipping threshold."""

    fee: Decimal
    free_above: Decimal

    def apply(self, subtotal: Decimal, quantity: int) -> Decimal:
        return (
            subtotal if subtotal >= self.free_above else subtotal + self.fee
        )


class PriceCalculator:
    """Applies rules in order. New behaviour = new rule, no subclassing."""

    def __init__(self, rules: Sequence[PricingRule] = ()) -> None:
        self._rules = tuple(rules)

    def total(self, unit_price: Decimal, quantity: int) -> Decimal:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        amount = unit_price * quantity
        for rule in self._rules:
            amount = rule.apply(amount, quantity)
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
