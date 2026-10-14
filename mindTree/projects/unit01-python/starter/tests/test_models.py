from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from quotes.models import Quote


def test_quote_is_immutable() -> None:
    quote = Quote("A", "s", Decimal("1"), 1)
    with pytest.raises(FrozenInstanceError):
        quote.unit_price = Decimal("2")  # type: ignore[misc]


@pytest.mark.parametrize(
    ("price", "available"), [(Decimal("0"), 1), (Decimal("1"), -1)]
)
def test_quote_rejects_invalid_values(
    price: Decimal, available: int
) -> None:
    with pytest.raises(ValueError):
        Quote("A", "s", price, available)
