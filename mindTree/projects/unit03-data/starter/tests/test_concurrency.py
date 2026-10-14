"""Two customers race for the last unit. Exactly one may win.

Runs only against PostgreSQL (real row locks); SQLite serialises
writes for the whole database, which hides the race."""


import pytest
from sqlalchemy import Engine

from tests.conftest import IS_POSTGRES

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES, reason="needs TEST_DATABASE_URL=postgresql+psycopg://"
)


def test_last_unit_is_sold_once(engine: Engine) -> None:
    # TODO: set MN-27 stock to 1, run 8 concurrent place_order calls in
    # a ThreadPoolExecutor (one session per thread via
    # make_session_factory) and assert exactly one succeeds and the
    # final stock is 0.
    pytest.skip("TODO: implement the concurrency test")
