"""FastAPI app wiring the data layer. Run:
uvicorn app.main:create_app --factory --reload"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache import InMemoryProductCache, ProductCache, RedisProductCache
from app.config import Settings, get_settings
from app.db import Base, make_engine, make_session_factory, session_scope
from app.errors import ConflictError, register_error_handlers
from app.repositories import CustomerRepository, ProductRepository
from app.schemas import (
    CustomerIn,
    CustomerOut,
    OrderIn,
    OrderOut,
    ProductOut,
)
from app.services.catalog import CatalogService
from app.services.orders import OrderService


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


def get_cache(request: Request) -> ProductCache:
    cache: ProductCache = request.app.state.cache
    return cache


SessionDep = Annotated[Session, Depends(get_session)]
CacheDep = Annotated[ProductCache, Depends(get_cache)]


def create_app(
    settings: Settings | None = None, *, create_schema: bool = True
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings)
        if create_schema:
            # Dev convenience only. Real environments run
            # `alembic upgrade head` as a deploy step.
            Base.metadata.create_all(engine)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        app.state.cache = (
            RedisProductCache(
                settings.redis_url, settings.cache_ttl_seconds
            )
            if settings.redis_url
            else InMemoryProductCache(settings.cache_ttl_seconds)
        )
        yield
        engine.dispose()  # close pooled connections

    app = FastAPI(title="Orders Data API", lifespan=lifespan)
    register_error_handlers(app)

    # Sync `def` endpoints: SQLAlchemy sync sessions block, so FastAPI
    # runs these in its threadpool instead of on the event loop.
    @app.get("/health")
    def health(session: SessionDep) -> dict[str, str]:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "up"}

    @app.post("/customers", status_code=status.HTTP_201_CREATED)
    def create_customer(
        body: CustomerIn, session: SessionDep
    ) -> CustomerOut:
        try:
            with session.begin():
                customer = CustomerRepository(session).add(
                    body.name, body.email.lower()
                )
        except IntegrityError as exc:
            # The UNIQUE constraint is the source of truth; checking
            # first and inserting second would race.
            raise ConflictError("Email already registered.") from exc
        return CustomerOut.model_validate(customer)

    @app.get("/products/{sku}")
    def get_product(
        sku: str, session: SessionDep, cache: CacheDep, response: Response
    ) -> ProductOut:
        product, hit = CatalogService(
            ProductRepository(session), cache
        ).get_product(sku)
        response.headers["X-Cache"] = "HIT" if hit else "MISS"
        return product

    @app.post("/orders", status_code=status.HTTP_201_CREATED)
    def place_order(
        body: OrderIn, session: SessionDep, cache: CacheDep
    ) -> OrderOut:
        return OrderService(session, cache).place_order(body)

    @app.get("/customers/{customer_id}/orders")
    def list_orders(
        customer_id: int, session: SessionDep, cache: CacheDep
    ) -> list[OrderOut]:
        return OrderService(session, cache).list_for_customer(customer_id)

    return app
