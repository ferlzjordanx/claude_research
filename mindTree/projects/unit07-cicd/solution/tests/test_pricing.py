from decimal import Decimal

import pytest

from app.pricing import PricingError, discount_for, line_total


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [(1, "0"), (9, "0"), (10, "0.05"), (99, "0.05"), (100, "0.10")],
)
def test_discount_tiers_boundaries(quantity: int, expected: str) -> None:
    assert discount_for(quantity) == Decimal(expected)


def test_line_total_rounds_half_up_to_cents() -> None:
    # 19.99 * 12 = 239.88; minus 5% = 227.886 -> 227.89
    assert line_total(Decimal("19.99"), 12) == Decimal("227.89")


def test_line_total_without_discount() -> None:
    assert line_total(Decimal("2.50"), 3) == Decimal("7.50")


def test_custom_tiers() -> None:
    tiers = ((2, Decimal("0.50")),)
    assert line_total(Decimal("10"), 2, tiers) == Decimal("10.00")


@pytest.mark.parametrize(
    ("price", "quantity"), [(Decimal("1"), 0), (Decimal("-0.01"), 1)]
)
def test_invalid_inputs(price: Decimal, quantity: int) -> None:
    with pytest.raises(PricingError):
        line_total(price, quantity)
