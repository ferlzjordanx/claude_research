"""Order placement: one transaction, atomic stock decrement."""

from __future__ import annotations

from collections import Counter  # noqa: F401
from decimal import Decimal  # noqa: F401

from sqlalchemy import update  # noqa: F401
from sqlalchemy.orm import Session

from app.cache import ProductCache
from app.errors import (
    NotFoundError,
)
from app.models import Customer, Order, OrderItem, Product  # noqa: F401
from app.repositories import (  # noqa: F401
    OrderRepository,
    ProductRepository,
)
from app.schemas import OrderIn, OrderLineOut, OrderOut
from app.services.catalog import cache_key  # noqa: F401


def to_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status,
        total=order.total,
        created_at=order.created_at,
        lines=[
            OrderLineOut(
                sku=item.product.sku,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items
        ],
    )


class OrderService:
    def __init__(self, session: Session, cache: ProductCache) -> None:
        self._session = session
        self._cache = cache

    def place_order(self, data: OrderIn) -> OrderOut:
        # TODO: implement order placement as ONE transaction:
        # 1. merge duplicate SKUs (collections.Counter)
        # 2. `with self._session.begin():` so any exception rolls back
        # 3. NotFoundError if the customer does not exist
        # 4. UnknownSkuError (422) listing SKUs that do not exist
        # 5. for each SKU in sorted order run an atomic conditional
        #    UPDATE products SET stock = stock - :qty
        #    WHERE sku = :sku AND stock >= :qty RETURNING id, price
        #    -> no row returned means InsufficientStockError
        # 6. build Order + OrderItem rows, compute the total, add()
        # 7. after commit, delete the product cache keys
        raise NotImplementedError

    def list_for_customer(self, customer_id: int) -> list[OrderOut]:
        if self._session.get(Customer, customer_id) is None:
            raise NotFoundError(f"Customer {customer_id} not found.")
        orders = OrderRepository(self._session).list_for_customer(
            customer_id
        )
        return [to_out(o) for o in orders]
