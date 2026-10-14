"""Ticket rules, including object-level authorization."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db import TicketRow
from app.errors import ForbiddenError, NotFoundError  # noqa: F401
from app.schemas import Role, TicketCreate, TicketStatus, User  # noqa: F401


class TicketService:
    def __init__(self, session: Session, user: User) -> None:
        self._session = session
        self._user = user

    def _visible(self) -> Select[TicketRow]:
        """Requesters only ever see their own tickets: the filter is
        part of the query, so other rows can never leak."""
        # TODO(1): requesters must only see rows they own. Add the filter
        # HERE (in the query), so list/get/update all inherit it.
        return select(TicketRow)

    def list(
        self, status: TicketStatus | None, limit: int, offset: int
    ) -> tuple[list[TicketRow], int]:
        stmt = self._visible()
        if status is not None:
            stmt = stmt.where(TicketRow.status == status.value)
        total = self._session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        rows = self._session.scalars(
            stmt.order_by(TicketRow.id.desc()).limit(limit).offset(offset)
        ).all()
        return list(rows), int(total or 0)

    def get(self, ticket_id: int) -> TicketRow:
        row = self._session.scalar(
            self._visible().where(TicketRow.id == ticket_id)
        )
        if row is None:
            # 404, not 403: don't reveal that someone else's ticket exists
            raise NotFoundError(f"Ticket {ticket_id} not found.")
        return row

    def create(self, data: TicketCreate) -> TicketRow:
        row = TicketRow(
            title=data.title,
            description=data.description,
            priority=data.priority.value,
            owner=self._user.username,  # from the token, never the body
        )
        with self._session.begin():
            self._session.add(row)
        return row

    def update_status(
        self, ticket_id: int, status: TicketStatus
    ) -> TicketRow:
        # TODO(2): only agents may change status -> raise ForbiddenError.
        with self._session.begin():
            row = self.get(ticket_id)
            row.status = status.value
        return row
