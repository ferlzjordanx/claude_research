"""Domain logic: volume-discounted line totals.

Pure functions with no I/O are the cheapest thing to test, so they
are the bulk of the unit-test stage in CI.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")

# (minimum quantity, discount fraction), checked from largest first.
DEFAULT_TIERS: tuple[tuple[int, Decimal], ...] = (
    (100, Decimal("0.10")),
    (10, Decimal("0.05")),
)


class PricingError(ValueError):
    """Raised for inputs that cannot produce a valid price."""


def discount_for(
    quantity: int,
    tiers: tuple[tuple[int, Decimal], ...] = DEFAULT_TIERS,
) -> Decimal:
    for minimum, discount in sorted(tiers, reverse=True):
        if quantity >= minimum:
            return discount
    return Decimal("0")


def line_total(
    unit_price: Decimal,
    quantity: int,
    tiers: tuple[tuple[int, Decimal], ...] = DEFAULT_TIERS,
) -> Decimal:
    """Price for `quantity` units, discounted, rounded to cents."""
    if quantity < 1:
        raise PricingError("quantity must be at least 1")
    if unit_price < 0:
        raise PricingError("unit_price must not be negative")
    gross = unit_price * quantity
    net = gross * (Decimal("1") - discount_for(quantity, tiers))
    # Money: Decimal + explicit rounding, never float.
    return net.quantize(CENT, rounding=ROUND_HALF_UP)
