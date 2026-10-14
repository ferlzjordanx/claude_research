"""Report queries, with manual spans around service and DB work."""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry.trace import Span, SpanKind, Tracer
from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from app.db import Customer, Order
from app.errors import NotFoundError
from app.schemas import RevenueRow

type AggregateRow = tuple[int, str, int, int]


class ReportService:
    def __init__(self, session: Session, tracer: Tracer) -> None:
        self._session = session
        self._tracer = tracer

    @contextmanager
    def _db_span(self, operation: str, table: str) -> Iterator[Span]:
        """A CLIENT span per query, with OTel DB semantic attributes."""
        with self._tracer.start_as_current_span(
            f"{operation} {table}",
            kind=SpanKind.CLIENT,
            attributes={
                "db.system.name": "sqlite",
                "db.operation.name": operation,
                "db.collection.name": table,
            },
        ) as span:
            yield span

    @staticmethod
    def _aggregate() -> Select[int, str, int, int]:
        """One query: customers LEFT JOIN orders, grouped."""
        total = func.coalesce(func.sum(Order.amount_cents), 0)
        return (
            select(
                Customer.id,
                Customer.name,
                func.count(Order.id),
                total.label("total"),
            )
            .outerjoin(Order, Order.customer_id == Customer.id)
            .group_by(Customer.id, Customer.name)
        )

    @staticmethod
    def _row(r: AggregateRow) -> RevenueRow:
        return RevenueRow(
            customer_id=r[0], name=r[1], order_count=r[2], total_cents=r[3]
        )

    def customer_summary(self, customer_id: int) -> RevenueRow:
        with self._tracer.start_as_current_span(
            "reports.customer_summary",
            attributes={"app.customer_id": customer_id},
        ):
            stmt = self._aggregate().where(Customer.id == customer_id)
            with self._db_span("SELECT", "customers"):
                row = self._session.execute(stmt).one_or_none()
            if row is None:
                raise NotFoundError(f"Customer {customer_id} not found.")
            return self._row(row)

    def revenue_by_customer(self) -> list[RevenueRow]:
        with self._tracer.start_as_current_span(
            "reports.revenue_by_customer"
        ) as span:
            stmt = self._aggregate().order_by(desc("total"), Customer.id)
            with self._db_span("SELECT", "customers") as db_span:
                rows = self._session.execute(stmt).all()
                db_span.set_attribute(
                    "db.response.returned_rows", len(rows)
                )
            span.set_attribute("app.report.rows", len(rows))
            return [self._row(r) for r in rows]
