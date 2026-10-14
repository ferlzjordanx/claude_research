"""Order placement: one transaction, atomic stock decrement."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.cache import ProductCache
from app.errors import (
    InsufficientStockError,
    NotFoundError,
    UnknownSkuError,
)
from app.models import Customer, Order, OrderItem, Product
from app.repositories import OrderRepository, ProductRepository
from app.schemas import OrderIn, OrderLineOut, OrderOut
from app.services.catalog import cache_key


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
        quantities = Counter[str]()
        for line in data.lines:
            quantities[line.sku] += line.quantity  # merge duplicate SKUs

        # session.begin(): COMMIT if the block finishes, ROLLBACK if it
        # raises. Either every row changes or none does (atomicity).
        with self._session.begin():
            if self._session.get(Customer, data.customer_id) is None:
                raise NotFoundError(
                    f"Customer {data.customer_id} not found."
                )
            products = ProductRepository(self._session).get_by_skus(
                quantities
            )
            missing = sorted(set(quantities) - set(products))
            if missing:
                raise UnknownSkuError(f"Unknown SKUs: {', '.join(missing)}")

            order = Order(customer_id=data.customer_id, total=Decimal("0"))
            total = Decimal("0")
            # Sorted order = every transaction locks rows in the same
            # order, which prevents deadlocks between concurrent orders.
            for sku in sorted(quantities):
                qty = quantities[sku]
                # Conditional UPDATE is atomic: check and decrement happen
                # in one statement, so two concurrent orders cannot both
                # take the last unit (no read-then-write race).
                row = self._session.execute(
                    update(Product)
                    .where(Product.sku == sku, Product.stock >= qty)
                    .values(stock=Product.stock - qty)
                    .returning(Product.id, Product.price)
                ).one_or_none()
                if row is None:
                    raise InsufficientStockError(
                        f"Not enough stock for {sku}."
                    )
                order.items.append(
                    OrderItem(
                        product=products[sku],
                        quantity=qty,
                        unit_price=row.price,
                    )
                )
                total += row.price * qty
            order.total = total
            self._session.add(order)
        # Invalidate AFTER commit so readers never re-cache stale stock.
        self._cache.delete(*(cache_key(s) for s in quantities))
        return to_out(order)

    def list_for_customer(self, customer_id: int) -> list[OrderOut]:
        if self._session.get(Customer, customer_id) is None:
            raise NotFoundError(f"Customer {customer_id} not found.")
        orders = OrderRepository(self._session).list_for_customer(
            customer_id
        )
        return [to_out(o) for o in orders]
