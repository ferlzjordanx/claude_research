"""Two customers race for the last unit. Exactly one may win.

Runs only against PostgreSQL (real row locks); SQLite serialises
writes for the whole database, which hides the race."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.cache import InMemoryProductCache
from app.db import make_session_factory
from app.errors import InsufficientStockError
from app.models import Product
from app.schemas import OrderIn
from app.services.orders import OrderService
from tests.conftest import IS_POSTGRES

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES, reason="needs TEST_DATABASE_URL=postgresql+psycopg://"
)


def test_last_unit_is_sold_once(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with Session(engine) as session:
        session.query(Product).filter_by(sku="MN-27").update({"stock": 1})
        session.commit()

    def attempt(_: int) -> str:
        with factory() as session:
            service = OrderService(session, InMemoryProductCache(60))
            try:
                service.place_order(
                    OrderIn.model_validate(
                        {
                            "customer_id": 1,
                            "lines": [{"sku": "MN-27", "quantity": 1}],
                        }
                    )
                )
                return "ok"
            except InsufficientStockError:
                return "sold out"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    assert results.count("ok") == 1
    assert results.count("sold out") == 7
    with Session(engine) as session:
        stock = session.query(Product).filter_by(sku="MN-27").one().stock
        assert stock == 0
