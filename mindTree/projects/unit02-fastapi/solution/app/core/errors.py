"""Domain errors and their mapping to RFC 9457 problem details."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
PROBLEM_JSON = "application/problem+json"


class DomainError(Exception):
    """Base for errors the service layer raises on purpose."""

    status_code = status.HTTP_400_BAD_REQUEST
    title = "Bad request"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Not found"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"


def problem(
    status_code: int, title: str, detail: str, **extra: object
) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        **extra,
    }
    return JSONResponse(
        body, status_code=status_code, media_type=PROBLEM_JSON
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return problem(exc.status_code, exc.title, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "The request body or parameters are invalid.",
            errors=errors,
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log full details server-side; never leak stack traces to clients.
        log.exception(
            "unhandled error on %s %s", request.method, request.url
        )
        return problem(500, "Internal server error", "Unexpected error.")
