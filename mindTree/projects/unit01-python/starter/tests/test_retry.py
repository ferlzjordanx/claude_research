from unittest.mock import AsyncMock

import pytest

from quotes.errors import InvalidSkuError, TransientSupplierError
from quotes.retry import retry_async


async def test_returns_after_transient_failures() -> None:
    sleep = AsyncMock()
    func = AsyncMock(side_effect=[TransientSupplierError(), "ok"])
    wrapped = retry_async(attempts=3, sleep=sleep)(func)

    assert await wrapped() == "ok"
    assert func.await_count == 2
    sleep.assert_awaited_once()


async def test_raises_after_last_attempt() -> None:
    func = AsyncMock(side_effect=TransientSupplierError("down"))
    wrapped = retry_async(attempts=3, sleep=AsyncMock())(func)

    with pytest.raises(TransientSupplierError):
        await wrapped()
    assert func.await_count == 3


async def test_does_not_retry_permanent_errors() -> None:
    func = AsyncMock(side_effect=InvalidSkuError("nope"))
    wrapped = retry_async(attempts=5, sleep=AsyncMock())(func)

    with pytest.raises(InvalidSkuError):
        await wrapped()
    assert func.await_count == 1


# TODO: write test_backoff_delays_are_capped - every delay passed to the
# injected sleep must be between 0 and max_delay.


def test_rejects_zero_attempts() -> None:
    with pytest.raises(ValueError):
        retry_async(attempts=0)
