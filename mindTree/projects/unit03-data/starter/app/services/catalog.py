from __future__ import annotations

from app.cache import ProductCache
from app.errors import NotFoundError  # noqa: F401
from app.repositories import ProductRepository
from app.schemas import ProductOut


def cache_key(sku: str) -> str:
    return f"product:{sku}"


class CatalogService:
    def __init__(self, products: ProductRepository, cache: ProductCache):
        self._products = products
        self._cache = cache

    def get_product(self, sku: str) -> tuple[ProductOut, bool]:
        """Cache-aside: try cache, else DB then populate cache.

        Returns (product, served_from_cache)."""
        # TODO:
        # 1. look up cache_key(sku) in self._cache -> HIT: return it, True
        # 2. MISS: load from self._products; NotFoundError if missing
        # 3. store out.model_dump(mode="json") in the cache, return False
        raise NotImplementedError
