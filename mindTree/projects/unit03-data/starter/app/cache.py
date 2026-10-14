"""Cache-aside for product reads: Redis in production, dict in tests."""

from __future__ import annotations

import logging
import time
from typing import Any, Protocol

import redis

log = logging.getLogger(__name__)


class ProductCache(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def set(self, key: str, value: dict[str, Any]) -> None: ...
    def delete(self, *keys: str) -> None: ...


class InMemoryProductCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._data.get(key)
        if item is None or item[0] < time.monotonic():
            self._data.pop(key, None)
            return None
        return item[1]

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = (time.monotonic() + self._ttl, value)

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._data.pop(key, None)


class RedisProductCache:
    """A cache outage must degrade performance, never correctness, so
    every Redis error is logged and treated as a cache miss."""

    def __init__(self, url: str, ttl_seconds: int) -> None:
        self._client = redis.Redis.from_url(
            url, socket_timeout=0.2, socket_connect_timeout=0.2
        )
        self._ttl = ttl_seconds

    # TODO: implement get/set/delete. Use json for (de)serialisation
    # and `ex=self._ttl` on set. Catch redis.RedisError in every method,
    # log a warning and behave like a cache miss / no-op.
    def get(self, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def set(self, key: str, value: dict[str, Any]) -> None:
        raise NotImplementedError

    def delete(self, *keys: str) -> None:
        raise NotImplementedError
