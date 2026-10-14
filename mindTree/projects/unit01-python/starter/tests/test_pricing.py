from decimal import Decimal

import pytest

from quotes.pricing import BulkDiscount, FlatShipping, PriceCalculator


def test_no_rules_is_price_times_quantity() -> None:
    assert PriceCalculator().total(Decimal("2.50"), 4) == Decimal("10.00")


def test_rules_apply_in_order() -> None:
    calc = PriceCalculator(
        [
            BulkDiscount(10, Decimal("10")),
            FlatShipping(Decimal("5"), Decimal("100")),
        ]
    )
    # 10 * 9.00 = 90 -> 10% off = 81 -> below 100 so +5 shipping = 86
    assert calc.total(Decimal("9.00"), 10) == Decimal("86.00")


def test_bulk_discount_not_applied_below_threshold() -> None:
    rule = BulkDiscount(10, Decimal("10"))
    assert rule.apply(Decimal("50"), 9) == Decimal("50")


def test_rounds_half_up_to_cents() -> None:
    calc = PriceCalculator([BulkDiscount(1, Decimal("33.333"))])
    assert calc.total(Decimal("1.00"), 1) == Decimal("0.67")


@pytest.mark.parametrize("quantity", [0, -3])
def test_rejects_non_positive_quantity(quantity: int) -> None:
    with pytest.raises(ValueError):
        PriceCalculator().total(Decimal("1"), quantity)
