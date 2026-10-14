"""Message broker abstraction plus an in-memory implementation.

The in-memory broker behaves like SQS / RabbitMQ with manual acks:
at-least-once delivery. A message leaves the queue only when it is
acked. If the consumer crashes (no ack) the message becomes visible
again after the visibility timeout and is delivered AGAIN. After too
many deliveries it moves to a dead-letter list for a human to inspect.
"""

import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Message:
    id: str  # event id: the consumer's dedupe key
    type: str  # e.g. "OrderPaid"
    version: int  # schema version of `data`
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Delivery:
    message: Message
    receipt: str
    attempt: int  # 1 on first delivery, 2+ on redelivery


class Broker(Protocol):
    def publish(self, topic: str, message: Message) -> None: ...

    def receive(
        self, topic: str, max_messages: int = 10
    ) -> list[Delivery]: ...

    def ack(self, delivery: Delivery) -> None: ...

    def nack(self, delivery: Delivery) -> None: ...


@dataclass
class _InFlight:
    topic: str
    message: Message
    attempt: int
    deadline: float


class InMemoryBroker:
    def __init__(
        self,
        visibility_timeout_s: float = 30.0,
        max_deliveries: int = 5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.visibility_timeout_s = visibility_timeout_s
        self.max_deliveries = max_deliveries
        self._clock = clock
        self._ready: dict[str, deque[tuple[Message, int]]] = {}
        self._in_flight: dict[str, _InFlight] = {}
        self.dead_letters: dict[str, list[Message]] = {}

    def publish(self, topic: str, message: Message) -> None:
        self._queue(topic).append((message, 0))

    def receive(self, topic: str, max_messages: int = 10) -> list[Delivery]:
        self._requeue_expired()
        queue = self._queue(topic)
        out: list[Delivery] = []
        while queue and len(out) < max_messages:
            message, attempts = queue.popleft()
            if attempts >= self.max_deliveries:
                self.dead_letters.setdefault(topic, []).append(message)
                continue
            receipt = uuid.uuid4().hex
            self._in_flight[receipt] = _InFlight(
                topic,
                message,
                attempts + 1,
                self._clock() + self.visibility_timeout_s,
            )
            out.append(Delivery(message, receipt, attempts + 1))
        return out

    def ack(self, delivery: Delivery) -> None:
        # A late ack (after the timeout) finds nothing: the message was
        # already made visible again and WILL be delivered twice.
        self._in_flight.pop(delivery.receipt, None)

    def nack(self, delivery: Delivery) -> None:
        item = self._in_flight.pop(delivery.receipt, None)
        if item is not None:
            self._queue(item.topic).append((item.message, item.attempt))

    def pending(self, topic: str) -> int:
        """Ready plus in-flight messages for a topic."""
        in_flight = sum(
            1 for i in self._in_flight.values() if i.topic == topic
        )
        return len(self._queue(topic)) + in_flight

    def _queue(self, topic: str) -> deque[tuple[Message, int]]:
        return self._ready.setdefault(topic, deque())

    def _requeue_expired(self) -> None:
        now = self._clock()
        for receipt, item in list(self._in_flight.items()):
            if item.deadline <= now:
                del self._in_flight[receipt]
                self._queue(item.topic).append((item.message, item.attempt))
