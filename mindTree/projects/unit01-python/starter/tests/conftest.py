from decimal import Decimal

import pytest

from quotes.suppliers import FakeSupplier


@pytest.fixture
def cheap() -> FakeSupplier:
    return FakeSupplier("cheap", {"A": Decimal("1.00"), "B": Decimal("5")})


@pytest.fixture
def pricey() -> FakeSupplier:
    return FakeSupplier("pricey", {"A": Decimal("2.00"), "B": Decimal("4")})
