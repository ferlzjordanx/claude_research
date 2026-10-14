"""Notifications consumer: idempotent, because delivery is not.

The broker delivers at least once, so the same event can arrive twice
(relay re-publish, late ack, redelivery after a crash). The consumer
records each event id in `processed_events` IN THE SAME TRANSACTION
as its side effect. A duplicate hits the primary key and is skipped.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.exc import IntegrityError  # noqa: F401 (TODO 6)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from messaging.broker import Broker, Message

log = logging.getLogger("notifications")
KINDS = {"OrderPaid": "receipt", "PaymentFailed": "payment_failed"}


class NotificationsBase(DeclarativeBase):
    """A separate schema: this service owns its own data."""


class ProcessedEvent(NotificationsBase):
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class NotificationRow(NotificationsBase):
    """Stands in for 'send an email': one row per message sent."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int]
    kind: Mapped[str] = mapped_column(String(32))


class UnsupportedEventVersion(Exception):
    pass


class NotificationsConsumer:
    SUPPORTED_VERSION = 1

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def handle(self, message: Message) -> bool:
        """Apply the event once. Returns False for a duplicate."""
        if message.version > self.SUPPORTED_VERSION:
            # Do not guess at a newer schema: fail, retry, then DLQ.
            raise UnsupportedEventVersion(
                f"{message.type} v{message.version}"
            )
        # TODO(6): in ONE transaction, insert ProcessedEvent(event_id=
        # message.id) and flush(): a duplicate id raises IntegrityError
        # -> log and return False. Otherwise add a NotificationRow for
        # types in KINDS (order_id from message.data["order_id"]) and
        # return True. Unknown types: mark processed, send nothing.
        raise NotImplementedError("TODO(6)")


def consume_once(
    broker: Broker, topic: str, consumer: NotificationsConsumer
) -> int:
    """Receive a batch; ack what succeeded, nack what failed."""
    handled = 0
    for delivery in broker.receive(topic):
        try:
            consumer.handle(delivery.message)
        except Exception:
            log.exception(
                "event %s failed (attempt %d)",
                delivery.message.id,
                delivery.attempt,
            )
            broker.nack(delivery)
            continue
        broker.ack(delivery)  # ack only AFTER the commit
        handled += 1
    return handled
