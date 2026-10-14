"""Transactional outbox: write events with the data, publish later.

Never "commit the order, then publish to the broker": if the process
dies between the two, the event is lost (or, publishing first, the
event describes an order that was rolled back). Instead the event row
commits atomically with the order, and this relay publishes it.
"""

import json
import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from messaging.broker import Broker, Message
from orders.db import OutboxRow, utcnow

log = logging.getLogger("orders.outbox")
TOPIC = "orders"


def new_outbox_event(
    aggregate_id: str,
    event_type: str,
    data: dict[str, Any],
    version: int = 1,
) -> OutboxRow:
    """Build the row; the caller adds it to ITS open transaction."""
    return OutboxRow(
        id=str(uuid.uuid4()),
        aggregate_id=aggregate_id,
        event_type=event_type,
        version=version,
        payload=json.dumps(data, sort_keys=True),
    )


def relay_once(
    sessions: sessionmaker[Session],
    broker: Broker,
    batch_size: int = 100,
) -> int:
    """Publish unpublished events in order; mark each one sent.

    Crash after publish but before commit -> the event is published
    again on the next run. That is at-least-once, by design: the
    consumer dedupes by event id. (Postgres with several relays:
    add .with_for_update(skip_locked=True) to the select.)
    """
    published = 0
    with sessions() as session:
        rows = session.scalars(
            select(OutboxRow)
            .where(OutboxRow.published_at.is_(None))
            .order_by(OutboxRow.created_at, OutboxRow.id)
            .limit(batch_size)
        ).all()
        for row in rows:
            broker.publish(
                TOPIC,
                Message(
                    id=row.id,
                    type=row.event_type,
                    version=row.version,
                    data=json.loads(row.payload),
                ),
            )
            row.published_at = utcnow()
            session.commit()
            published += 1
    if published:
        log.info("relayed %d outbox event(s)", published)
    return published


def pending_count(sessions: sessionmaker[Session]) -> int:
    with sessions() as session:
        count = session.scalar(
            select(func.count())
            .select_from(OutboxRow)
            .where(OutboxRow.published_at.is_(None))
        )
        return count or 0
