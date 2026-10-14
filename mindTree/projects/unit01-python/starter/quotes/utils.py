"""Small helpers: a batching generator and a timing context manager."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

log = logging.getLogger(__name__)


def chunked[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield lists of at most ``size`` items, lazily (constant memory)."""
    # TODO: implement as a generator (use `yield`); reject size < 1.
    # Hint: itertools.islice takes the next N items from an iterator.
    raise NotImplementedError


@contextmanager
def timed(label: str) -> Iterator[dict[str, float]]:
    """Measure elapsed wall time; the result is available after exit."""
    # TODO: implement with time.perf_counter(); store elapsed seconds in
    # result["seconds"] even when the with-block raises (try/finally).
    result: dict[str, float] = {}
    yield result
