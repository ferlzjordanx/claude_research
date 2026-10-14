"""Cache-aside for product reads: Redis in production, dict in tests."""

from __future__ import annotations

import json
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

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self._client.get(key)
        except redis.RedisError as exc:
            log.warning("cache get failed: %s", exc)
            return None
        return json.loads(raw) if raw else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        try:
            self._client.set(key, json.dumps(value), ex=self._ttl)
        except redis.RedisError as exc:
            log.warning("cache set failed: %s", exc)

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            self._client.delete(*keys)
        except redis.RedisError as exc:
            log.warning("cache delete failed: %s", exc)
