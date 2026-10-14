"""RFC 9457 problem details shared by both services.

Sharing a tiny cross-cutting helper is fine. Sharing *domain* models
between services is not: it couples their release cycles.
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
PROBLEM_JSON = "application/problem+json"


class DomainError(Exception):
    """An error the service raises on purpose, mapped to a status."""

    status_code = 400
    title = "Bad request"

    def __init__(self, detail: str, **extra: object) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


def problem(
    status: int,
    title: str,
    detail: str,
    headers: dict[str, str] | None = None,
    **extra: object,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        **extra,
    }
    return JSONResponse(
        body, status, headers=headers, media_type=PROBLEM_JSON
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain(_: Request, exc: DomainError) -> JSONResponse:
        headers = exc.extra.pop("headers", None)
        return problem(
            exc.status_code,
            exc.title,
            exc.detail,
            headers=headers if isinstance(headers, dict) else None,
            **exc.extra,
        )

    @app.exception_handler(HTTPException)
    async def http(_: Request, exc: HTTPException) -> JSONResponse:
        return problem(
            exc.status_code,
            "Request failed",
            str(exc.detail),
            headers=dict(exc.headers) if exc.headers else None,
        )

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
