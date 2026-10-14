import itertools

import pytest

from quotes.utils import chunked, timed


def test_chunked_splits_with_remainder() -> None:
    assert list(chunked(range(5), 2)) == [[0, 1], [2, 3], [4]]


def test_chunked_is_lazy() -> None:
    # An infinite iterator works because chunked never materialises it.
    first = next(chunked(itertools.count(), 3))
    assert first == [0, 1, 2]


def test_chunked_rejects_bad_size() -> None:
    with pytest.raises(ValueError):
        list(chunked([1], 0))


def test_timed_records_even_on_error() -> None:
    with pytest.raises(RuntimeError):
        with timed("boom") as result:
            raise RuntimeError
    assert result["seconds"] >= 0
