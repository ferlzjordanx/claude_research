"""Async retry with exponential backoff and full jitter."""

from __future__ import annotations

import asyncio
import functools
import logging
import random
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from quotes.errors import TransientSupplierError

P = ParamSpec("P")
T = TypeVar("T")
log = logging.getLogger(__name__)


def retry_async(
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (TransientSupplierError,),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry an async function on *transient* errors only.

    ``sleep`` is injectable so tests run instantly and deterministically.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on as exc:
                    if attempt == attempts:
                        raise
                    # Full jitter: random delay in [0, capped exponential].
                    cap = min(max_delay, base_delay * 2 ** (attempt - 1))
                    delay = random.uniform(0, cap)
                    log.warning(
                        "attempt %d/%d failed (%s); retrying in %.3fs",
                        attempt,
                        attempts,
                        exc,
                        delay,
                    )
                    await sleep(delay)
            raise AssertionError("unreachable")  # pragma: no cover

        return wrapper

    return decorator
