from decimal import Decimal

from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Product
from app.repositories import OrderRepository


def test_list_orders_avoids_n_plus_one(engine: Engine) -> None:
    with Session(engine) as session:
        product = session.query(Product).filter_by(sku="KB-01").one()
        for _ in range(5):
            session.add(
                Order(
                    customer_id=1,
                    total=Decimal("89.00"),
                    items=[
                        OrderItem(
                            product=product,
                            quantity=1,
                            unit_price=Decimal("89.00"),
                        )
                    ],
                )
            )
        session.commit()

    statements: list[str] = []

    def count(*args: object) -> None:
        statements.append(str(args[2]))  # (conn, cursor, statement, ...)

    event.listen(engine, "before_cursor_execute", count)
    try:
        with Session(engine) as session:
            orders = OrderRepository(session).list_for_customer(1)
            skus = [i.product.sku for o in orders for i in o.items]
    finally:
        event.remove(engine, "before_cursor_execute", count)

    assert len(skus) == 5
    # orders + items + products = 3 queries, regardless of order count.
    assert len(statements) == 3
