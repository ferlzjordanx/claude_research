from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.observability import request_id_var

log = logging.getLogger(__name__)


class DomainError(Exception):
    status_code = 400
    title = "Bad request"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404
    title = "Not found"


class ForbiddenError(DomainError):
    status_code = 403
    title = "Forbidden"


class ConflictError(DomainError):
    status_code = 409
    title = "Conflict"


def problem(
    status: int, title: str, detail: str, **extra: object
) -> JSONResponse:
    # request_id lets the UI show "reference abc123" so support can
    # find the exact log lines for a user's failed request.
    body = {
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id_var.get(),
        **extra,
    }
    return JSONResponse(body, status, media_type="application/problem+json")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain(_: Request, exc: DomainError) -> JSONResponse:
        return problem(exc.status_code, exc.title, exc.detail)

    @app.exception_handler(HTTPException)
    async def http(_: Request, exc: HTTPException) -> JSONResponse:
        response = problem(
            exc.status_code, "Request failed", str(exc.detail)
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()
        ]
        return problem(
            422,
            "Validation failed",
            "The request is invalid.",
            errors=errors,
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s", request.url.path)
        return problem(500, "Internal server error", "Unexpected error.")
