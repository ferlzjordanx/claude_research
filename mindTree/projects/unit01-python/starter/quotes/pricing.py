"""Pricing rules composed into a calculator (composition > inheritance)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
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
        # TODO: implement - reduce subtotal by `percent` % when
        # quantity >= min_quantity, otherwise return subtotal unchanged.
        raise NotImplementedError


@dataclass(frozen=True)
class FlatShipping:
    """Adds a fixed shipping fee below a free-shipping threshold."""

    fee: Decimal
    free_above: Decimal

    def apply(self, subtotal: Decimal, quantity: int) -> Decimal:
        # TODO: implement - add `fee` unless subtotal >= free_above.
        raise NotImplementedError


class PriceCalculator:
    """Applies rules in order. New behaviour = new rule, no subclassing."""

    def __init__(self, rules: Sequence[PricingRule] = ()) -> None:
        self._rules = tuple(rules)

    def total(self, unit_price: Decimal, quantity: int) -> Decimal:
        # TODO: implement
        # 1. reject quantity <= 0 with ValueError
        # 2. start from unit_price * quantity
        # 3. apply each rule in order
        # 4. round to cents with ROUND_HALF_UP (Decimal.quantize)
        raise NotImplementedError
