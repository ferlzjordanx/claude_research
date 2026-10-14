from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Order, Product


def test_stock_cannot_go_negative(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(
            Product(sku="X", name="x", price=Decimal("1"), stock=-1)
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_order_requires_existing_customer(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(Order(customer_id=12345, total=Decimal("1")))
        with pytest.raises(IntegrityError):
            session.commit()
