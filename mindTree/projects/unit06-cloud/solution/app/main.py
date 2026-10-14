"""Inventory API. Run: uvicorn app.main:create_app --factory"""

# No `from __future__ import annotations` here: FastAPI must resolve the
# Annotated dependency aliases defined inside create_app at runtime.

import logging
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.config import Settings, get_settings
from app.db import Base, ItemRow, make_engine
from app.health import HealthState, check_ready
from app.logging_config import configure_logging
from app.schemas import ItemCreate, ItemOut, VersionOut

log = logging.getLogger("app")
access = logging.getLogger("access")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    health = HealthState()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        if settings.create_schema:
            try:
                Base.metadata.create_all(engine)
            except SQLAlchemyError as exc:
                # Do not crash-loop on a DB blip: start, report 503 on
                # /health/ready, and let Kubernetes hold traffic back.
                log.error(
                    "schema creation failed; not ready",
                    extra={"error": type(exc).__name__},
                )
        app.state.engine = engine
        app.state.session_factory = sessionmaker(
            engine, expire_on_commit=False
        )
        log.info(
            "started",
            extra={"version": settings.version, "sha": settings.git_sha},
        )
        yield
        # Reached after SIGTERM: uvicorn has stopped accepting new
        # connections and waited for in-flight requests (bounded by
        # --timeout-graceful-shutdown). Report not-ready for anything
        # still probing, then release DB connections.
        health.begin_drain()
        engine.dispose()
        log.info("stopped")

    app = FastAPI(
        title="Inventory API", version=settings.version, lifespan=lifespan
    )
    app.state.health = health

    @app.middleware("http")
    async def access_log(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        if not request.url.path.startswith("/health"):
            # Probes hit every few seconds; logging them is noise.
            access.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
        return response

    def get_session(request: Request) -> Iterator[Session]:
        factory: sessionmaker[Session] = request.app.state.session_factory
        with factory() as session:
            yield session

    SessionDep = Annotated[Session, Depends(get_session)]

    @app.get("/health/live", tags=["ops"])
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["ops"])
    def ready(request: Request) -> JSONResponse:
        ok, details = check_ready(
            request.app.state.health, request.app.state.engine
        )
        code = status.HTTP_200_OK if ok else 503
        return JSONResponse(details, status_code=code)

    @app.get("/version", tags=["ops"])
    def version() -> VersionOut:
        return VersionOut(
            version=settings.version,
            git_sha=settings.git_sha,
            environment=settings.environment,
        )

    @app.get("/items", tags=["items"])
    def list_items(session: SessionDep) -> list[ItemOut]:
        rows = session.scalars(select(ItemRow).order_by(ItemRow.id))
        return [ItemOut.model_validate(r) for r in rows]

    @app.post("/items", status_code=status.HTTP_201_CREATED, tags=["items"])
    def create_item(body: ItemCreate, session: SessionDep) -> ItemOut:
        row = ItemRow(**body.model_dump())
        session.add(row)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                409, f"SKU {body.sku!r} already exists"
            ) from exc
        return ItemOut.model_validate(row)

    @app.get("/items/{item_id}", tags=["items"])
    def get_item(item_id: int, session: SessionDep) -> ItemOut:
        row = session.get(ItemRow, item_id)
        if row is None:
            raise HTTPException(404, f"Item {item_id} not found")
        return ItemOut.model_validate(row)

    return app
