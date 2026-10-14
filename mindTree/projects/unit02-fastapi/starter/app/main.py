"""Application factory: wiring only, no business logic."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import routes_auth, routes_customers
from app.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.repositories.customer_repo import InMemoryCustomerRepository
from app.repositories.user_repo import InMemoryUserRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    """Run with: uvicorn app.main:create_app --factory --reload"""
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup: build long-lived resources once (DB pools, clients).
        app.state.customer_repo = InMemoryCustomerRepository()
        app.state.user_repo = InMemoryUserRepository.from_spec(
            settings.demo_users if settings.env != "prod" else ""
        )
        yield
        # Shutdown: close pools/clients here.

    app = FastAPI(
        title="Customers API",
        version="1.0.0",
        lifespan=lifespan,
        description="Unit 2 project: secured customer CRUD.",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    register_error_handlers(app)
    app.include_router(routes_auth.router)
    app.include_router(routes_customers.router)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
