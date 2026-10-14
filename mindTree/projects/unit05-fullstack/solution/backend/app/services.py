"""Ticket rules, including object-level authorization."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db import TicketRow
from app.errors import ForbiddenError, NotFoundError
from app.schemas import Role, TicketCreate, TicketStatus, User


class TicketService:
    def __init__(self, session: Session, user: User) -> None:
        self._session = session
        self._user = user

    def _visible(self) -> Select[TicketRow]:
        """Requesters only ever see their own tickets: the filter is
        part of the query, so other rows can never leak."""
        stmt = select(TicketRow)
        if self._user.role is Role.REQUESTER:
            stmt = stmt.where(TicketRow.owner == self._user.username)
        return stmt

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
        if self._user.role is not Role.AGENT:
            raise ForbiddenError("Only agents can change ticket status.")
        with self._session.begin():
            row = self.get(ticket_id)
            row.status = status.value
        return row
