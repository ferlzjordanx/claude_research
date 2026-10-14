"""Async retry with exponential backoff and full jitter."""

from __future__ import annotations

import asyncio
import functools
import logging
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
            # TODO: implement
            # - call `await func(*args, **kwargs)` up to `attempts` times
            # - only catch exceptions listed in `retry_on`
            # - re-raise on the last attempt
            # - between attempts await sleep(delay) where delay is a
            #   random value in [0, min(max_delay, base_delay * 2**(n-1))]
            raise NotImplementedError

        return wrapper

    return decorator
