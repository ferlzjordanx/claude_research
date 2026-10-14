"""Small helpers: a batching generator and a timing context manager."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from itertools import islice

log = logging.getLogger(__name__)


def chunked[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield lists of at most ``size`` items, lazily (constant memory)."""
    if size < 1:
        raise ValueError("size must be >= 1")
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


@contextmanager
def timed(label: str) -> Iterator[dict[str, float]]:
    """Measure elapsed wall time; the result is available after exit."""
    result: dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        # finally runs on success AND on exceptions, like a with-block
        # guarantee for cleanup.
        result["seconds"] = time.perf_counter() - start
        log.info("%s took %.3fs", label, result["seconds"])
