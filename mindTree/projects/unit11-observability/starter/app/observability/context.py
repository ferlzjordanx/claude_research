"""Request-scoped context: the request ID lives in a ContextVar."""

from contextvars import ContextVar

# A ContextVar is per asyncio task (and copied into threads started by
# asyncio.to_thread / Starlette's threadpool), so concurrent requests
# never see each other's IDs. "-" means "outside a request".
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
