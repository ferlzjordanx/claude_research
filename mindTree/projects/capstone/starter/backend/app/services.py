"""Ticket and reply rules, including object-level authorization."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.ai.assistant import Draft, OrderLookup
from app.ai.triage import TriageOutcome
from app.db import OrderRow, ReplyRow, TicketRow
from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.schemas import (
    AiTriageOut,
    Role,
    TicketCreate,
    TicketOut,
    TicketStatus,
    User,
)


class TicketService:
    def __init__(self, session: Session, user: User) -> None:
        self._session = session
        self._user = user

    @contextmanager
    def _write(self) -> Iterator[None]:
        """Commit on success, roll back on error. The session autobegins
        on first use, so reads + writes share one transaction."""
        try:
            yield
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def release(self) -> None:
        """End the current read transaction. Call before slow external
        work (LLM calls) so no DB transaction stays open meanwhile."""
        self._session.commit()

    @property
    def is_agent(self) -> bool:
        return self._user.role is Role.AGENT

    def require_agent(self) -> None:
        if not self.is_agent:
            raise ForbiddenError("Only agents can do this.")

    def _visible(self) -> Select[TicketRow]:
        stmt = select(TicketRow)
        if not self.is_agent:
            stmt = stmt.where(TicketRow.owner == self._user.username)
        return stmt

    def to_out(self, row: TicketRow) -> TicketOut:
        out = TicketOut.model_validate(row)
        # AI triage is an internal aid for agents, not shown to
        # requesters.
        if self.is_agent:
            out.ai = AiTriageOut(
                status=row.ai_status,
                category=row.ai_category,
                priority=row.ai_priority,
                summary=row.ai_summary,
                confidence=row.ai_confidence,
                needs_human=row.ai_needs_human,
            )
        return out

    def search(
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
            raise NotFoundError(f"Ticket {ticket_id} not found.")
        return row

    def create(
        self, data: TicketCreate, triage: TriageOutcome
    ) -> TicketRow:
        row = TicketRow(
            title=data.title,
            description=data.description,
            priority=data.priority.value,
            owner=self._user.username,
        )
        self._apply_triage(row, triage)
        with self._write():
            self._session.add(row)
        return row

    def save_triage(
        self, ticket_id: int, triage: TriageOutcome
    ) -> TicketRow:
        self.require_agent()
        with self._write():
            row = self.get(ticket_id)
            self._apply_triage(row, triage)
        return row

    @staticmethod
    def _apply_triage(row: TicketRow, triage: TriageOutcome) -> None:
        row.ai_status = triage.status
        row.ai_needs_human = triage.needs_human
        if triage.result is not None:
            row.ai_category = triage.result.category.value
            row.ai_priority = triage.result.priority.value
            row.ai_summary = triage.result.summary
            row.ai_confidence = triage.result.confidence

    def update_status(
        self, ticket_id: int, status: TicketStatus
    ) -> TicketRow:
        self.require_agent()
        with self._write():
            row = self.get(ticket_id)
            row.status = status.value
        return row

    # ------------------------------------------------------- replies

    def replies(self, ticket_id: int) -> list[ReplyRow]:
        self.get(ticket_id)  # visibility check first
        stmt = select(ReplyRow).where(ReplyRow.ticket_id == ticket_id)
        # TODO(6): requesters must never see drafts (status "sent" only).
        return list(self._session.scalars(stmt.order_by(ReplyRow.id)))

    def order_lookup(self, ticket: TicketRow) -> OrderLookup:
        """Snapshot of the ticket OWNER's orders for the assistant tool.

        Authorization is built in: other customers' orders are simply
        not in the snapshot. Loading up front also keeps DB access out
        of the async agent loop.
        """
        # TODO(5): load ONLY the ticket owner's orders into a dict
        # {id: {"id", "status", "eta"}} and return its .get. Other
        # customers' orders must be invisible to the assistant.
        orders = {
            o.id: {"id": o.id, "status": o.status, "eta": o.eta}
            for o in self._session.scalars(select(OrderRow))
        }
        return orders.get

    def save_draft(self, ticket_id: int, draft: Draft) -> ReplyRow:
        self.require_agent()
        reply = ReplyRow(
            ticket_id=ticket_id,
            body=draft.body,
            citations=draft.citations,
            status="draft",
            ai_generated=True,
            created_by=self._user.username,
        )
        with self._write():
            self.get(ticket_id)
            self._session.add(reply)
        return reply

    def add_reply(self, ticket_id: int, body: str) -> ReplyRow:
        self.require_agent()
        reply = ReplyRow(
            ticket_id=ticket_id,
            body=body,
            citations=[],
            status="sent",
            created_by=self._user.username,
            approved_by=self._user.username,
        )
        with self._write():
            self.get(ticket_id)
            self._session.add(reply)
        return reply

    def send_draft(self, reply_id: int, body: str | None) -> ReplyRow:
        """Human approval: the only way AI text reaches a customer."""
        self.require_agent()
        with self._write():
            reply = self._session.get(ReplyRow, reply_id)
            if reply is None:
                raise NotFoundError(f"Reply {reply_id} not found.")
            # TODO(7): a reply that is not a draft -> ConflictError (409).
            _ = ConflictError
            if body is not None:
                reply.body = body
            reply.status = "sent"
            reply.approved_by = self._user.username
        return reply
