from __future__ import annotations

from app.cache import ProductCache
from app.errors import NotFoundError
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
        cached = self._cache.get(cache_key(sku))
        if cached is not None:
            return ProductOut.model_validate(cached), True
        product = self._products.get_by_sku(sku)
        if product is None:
            raise NotFoundError(f"Product {sku} not found.")
        out = ProductOut.model_validate(product)
        self._cache.set(cache_key(sku), out.model_dump(mode="json"))
        return out, False
