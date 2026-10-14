import time

from app.cache import InMemoryProductCache, RedisProductCache


def test_in_memory_cache_expires() -> None:
    cache = InMemoryProductCache(ttl_seconds=0)
    cache.set("k", {"a": 1})
    time.sleep(0.01)
    assert cache.get("k") is None


def test_redis_outage_degrades_to_cache_miss() -> None:
    # Nothing listens on port 1: every call fails fast and is swallowed.
    cache = RedisProductCache("redis://127.0.0.1:1/0", ttl_seconds=60)
    cache.set("k", {"a": 1})
    assert cache.get("k") is None
    cache.delete("k")
