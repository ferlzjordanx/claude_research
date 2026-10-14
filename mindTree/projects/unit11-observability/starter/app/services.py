"""Report queries, with manual spans around service and DB work."""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry.trace import INVALID_SPAN, Span, Tracer
from sqlalchemy import Select, func, select
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
        # TODO(4a): start a span named f"{operation} {table}" with
        # kind=SpanKind.CLIENT and attributes db.system.name="sqlite",
        # db.operation.name=operation, db.collection.name=table, using
        # self._tracer.start_as_current_span(...); yield that span.
        yield INVALID_SPAN

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
        # TODO(4b): wrap this method in a span named
        # "reports.revenue_by_customer", run the query inside
        # self._db_span("SELECT", "customers"), and set the attributes
        # db.response.returned_rows (on the DB span) and
        # app.report.rows (on the service span) to the row count.
        #
        # TODO(5): BUG - N+1 queries. This runs 1 query for customers
        # plus 1 lazy-load query PER customer (`customer.orders`).
        # Replace it with ONE aggregate query: use self._aggregate()
        # ordered by desc("total"), then Customer.id.
        customers = self._session.scalars(
            select(Customer).order_by(Customer.id)
        ).all()
        rows = [
            RevenueRow(
                customer_id=c.id,
                name=c.name,
                order_count=len(c.orders),  # lazy load: 1 query each
                total_cents=sum(o.amount_cents for o in c.orders),
            )
            for c in customers
        ]
        rows.sort(key=lambda r: (-r.total_cents, r.customer_id))
        return rows
