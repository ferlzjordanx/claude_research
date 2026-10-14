"""Domain errors and RFC 9457 problem+json responses."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.observability.context import request_id_var

PROBLEM_JSON = "application/problem+json"


class AppError(Exception):
    status = 500
    title = "Internal Server Error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status = 404
    title = "Not Found"


class UpstreamError(AppError):
    status = 502
    title = "Bad Gateway"


class UpstreamTimeoutError(AppError):
    status = 504
    title = "Gateway Timeout"


def problem(
    request: Request, status: int, title: str, detail: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type=PROBLEM_JSON,
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
            "request_id": request_id_var.get(),
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    async def on_app_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        assert isinstance(exc, AppError)
        return problem(request, exc.status, exc.title, exc.detail)

    async def on_validation(
        request: Request, exc: Exception
    ) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        return problem(
            request, 422, "Validation Error", f"{where}: {first['msg']}"
        )

    app.add_exception_handler(AppError, on_app_error)
    app.add_exception_handler(RequestValidationError, on_validation)
