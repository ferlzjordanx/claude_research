from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400
    title = "Bad request"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404
    title = "Not found"


class ConflictError(DomainError):
    status_code = 409
    title = "Conflict"


class InsufficientStockError(ConflictError):
    title = "Insufficient stock"


class UnknownSkuError(DomainError):
    status_code = 422
    title = "Unknown SKU"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            {
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
            },
            status_code=exc.status_code,
            media_type="application/problem+json",
        )
