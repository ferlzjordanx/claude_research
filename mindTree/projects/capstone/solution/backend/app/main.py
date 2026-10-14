"""Acme Support Copilot API.

Run: uvicorn app.main:create_app --factory --reload
"""

# No `from __future__ import annotations`: FastAPI must resolve the
# Annotated dependency aliases defined inside create_app at runtime.

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

import anthropic
import openai
from anyio.from_thread import run as run_async
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.ai.assistant import Assistant
from app.ai.fake import FakeLLM
from app.ai.kb import KnowledgeBase
from app.ai.llm import LLM, AnthropicLLM, OpenAILLM
from app.ai.triage import TriageService
from app.config import Settings, get_settings
from app.db import Base, OrderRow, UserRow, make_engine, session_scope
from app.errors import register_error_handlers
from app.observability import (
    Metrics,
    ObservabilityMiddleware,
    configure_logging,
)
from app.schemas import (
    DraftOut,
    ReplyCreate,
    ReplyOut,
    Role,
    TicketCreate,
    TicketOut,
    TicketPage,
    TicketStatus,
    TicketStatusUpdate,
    Token,
    User,
)
from app.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hasher,
)
from app.services import TicketService

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")
DEMO_ORDERS = [
    ("ORD-1001", "alice", "in_transit", "2026-10-16"),
    ("ORD-1002", "bob", "delivered", None),
    ("ORD-1003", "alice", "delayed", "2026-10-20"),
]


def build_llm(settings: Settings) -> LLM:
    """Pick the provider from config. SDK retries are disabled because
    TriageService owns the retry policy (never stack retry layers)."""
    if settings.llm_provider == "anthropic":
        if settings.anthropic_api_key is None:
            raise ValueError("APP_ANTHROPIC_API_KEY is required")
        return AnthropicLLM(
            anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key.get_secret_value(),
                timeout=settings.llm_timeout_s,
                max_retries=0,
            ),
            settings.anthropic_model,
        )
    if settings.llm_provider == "openai":
        if settings.openai_api_key is None:
            raise ValueError("APP_OPENAI_API_KEY is required")
        return OpenAILLM(
            openai.AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=settings.llm_timeout_s,
                max_retries=0,
            ),
            settings.openai_model,
        )
    return FakeLLM()


def seed(factory: sessionmaker[Session], spec: str) -> None:
    with factory.begin() as session:
        for item in filter(None, (s.strip() for s in spec.split(","))):
            username, password, role = item.split(":")
            if session.get(UserRow, username) is None:
                session.add(
                    UserRow(
                        username=username,
                        password_hash=hasher.hash(password),
                        role=Role(role).value,
                    )
                )
    with factory.begin() as session:
        for oid, customer, status, eta in DEMO_ORDERS:
            if session.get(UserRow, customer) and not session.get(
                OrderRow, oid
            ):
                session.add(
                    OrderRow(
                        id=oid, customer=customer, status=status, eta=eta
                    )
                )


def create_app(
    settings: Settings | None = None, llm: LLM | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_json)
    metrics = Metrics()
    model = llm or build_llm(settings)  # fail fast on bad config
    kb = KnowledgeBase.from_dir(settings.kb_dir)
    triage = TriageService(
        model,
        metrics,
        settings.llm_timeout_s,
        settings.llm_max_retries,
        settings.llm_retry_base_s,
    )
    assistant = Assistant(
        model,
        kb,
        metrics,
        settings.agent_max_turns,
        settings.llm_timeout_s * 2,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        if settings.create_schema:
            Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        if settings.env != "prod" and settings.demo_users:
            seed(factory, settings.demo_users)
        app.state.session_factory = factory
        yield
        engine.dispose()

    app = FastAPI(
        title="Acme Support Copilot API",
        version=settings.version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(ObservabilityMiddleware, metrics=metrics)
    register_error_handlers(app)

    def get_session(request: Request) -> Iterator[Session]:
        yield from session_scope(request.app.state.session_factory)

    SessionDep = Annotated[Session, Depends(get_session)]

    def current_user(token: Annotated[str, Depends(oauth2)]) -> User:
        try:
            return decode_access_token(token, settings)
        except InvalidTokenError as exc:
            raise HTTPException(
                401,
                "Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    UserDep = Annotated[User, Depends(current_user)]

    def tickets(session: SessionDep, user: UserDep) -> TicketService:
        return TicketService(session, user)

    TicketsDep = Annotated[TicketService, Depends(tickets)]

    # ------------------------------------------------------------ ops

    @app.get("/health/live", tags=["ops"])
    def live() -> dict[str, str]:
        return {"status": "alive"}  # no dependency checks: see Unit 6

    @app.get("/health", tags=["ops"])
    def ready(session: SessionDep) -> dict[str, str]:
        session.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/version", tags=["ops"])
    def version() -> dict[str, str]:
        return {
            "version": settings.version,
            "git_sha": settings.git_sha,
            "llm_provider": model.name,
        }

    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    def prometheus() -> Response:
        return Response(
            generate_latest(metrics.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    # ----------------------------------------------------------- auth

    @app.post("/auth/token", tags=["auth"])
    def login(
        form: Annotated[OAuth2PasswordRequestForm, Depends()],
        session: SessionDep,
    ) -> Token:
        row = session.scalar(
            select(UserRow).where(UserRow.username == form.username)
        )
        if row is None or not hasher.verify(
            form.password, row.password_hash
        ):
            raise HTTPException(
                401,
                "Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = User(username=row.username, role=Role(row.role))
        return Token(
            access_token=create_access_token(user, settings),
            expires_in=settings.access_token_minutes * 60,
        )

    @app.get("/me", tags=["auth"])
    def me(user: UserDep) -> User:
        return user

    # -------------------------------------------------------- tickets
    # Endpoints are plain `def` (FastAPI runs them in a thread pool, so
    # sync SQLAlchemy never blocks the event loop). Async AI calls are
    # bridged back to the loop with anyio's from_thread.run.

    @app.get("/tickets", tags=["tickets"])
    def list_tickets(
        service: TicketsDep,
        status_: Annotated[
            TicketStatus | None, Query(alias="status")
        ] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> TicketPage:
        rows, total = service.search(status_, limit, offset)
        return TicketPage(
            items=[service.to_out(r) for r in rows], total=total
        )

    @app.post("/tickets", status_code=201, tags=["tickets"])
    def create_ticket(body: TicketCreate, service: TicketsDep) -> TicketOut:
        # Triage BEFORE the transaction: never hold a DB transaction
        # open while waiting on a slow external call.
        outcome = run_async(triage.triage, body.title, body.description)
        return service.to_out(service.create(body, outcome))

    @app.get("/tickets/{ticket_id}", tags=["tickets"])
    def get_ticket(ticket_id: int, service: TicketsDep) -> TicketOut:
        return service.to_out(service.get(ticket_id))

    @app.patch("/tickets/{ticket_id}", tags=["tickets"])
    def update_ticket(
        ticket_id: int, body: TicketStatusUpdate, service: TicketsDep
    ) -> TicketOut:
        return service.to_out(service.update_status(ticket_id, body.status))

    @app.post("/tickets/{ticket_id}/retriage", tags=["ai"])
    def retriage(ticket_id: int, service: TicketsDep) -> TicketOut:
        service.require_agent()
        row = service.get(ticket_id)
        service.release()
        outcome = run_async(triage.triage, row.title, row.description)
        return service.to_out(service.save_triage(ticket_id, outcome))

    # -------------------------------------------------------- replies

    @app.get("/tickets/{ticket_id}/replies", tags=["replies"])
    def list_replies(ticket_id: int, service: TicketsDep) -> list[ReplyOut]:
        return [
            ReplyOut.model_validate(r) for r in service.replies(ticket_id)
        ]

    @app.post(
        "/tickets/{ticket_id}/replies", status_code=201, tags=["replies"]
    )
    def add_reply(
        ticket_id: int, body: ReplyCreate, service: TicketsDep
    ) -> ReplyOut:
        return ReplyOut.model_validate(
            service.add_reply(ticket_id, body.body)
        )

    @app.post("/tickets/{ticket_id}/draft", status_code=201, tags=["ai"])
    def draft_reply(ticket_id: int, service: TicketsDep) -> DraftOut:
        service.require_agent()
        row = service.get(ticket_id)
        lookup = service.order_lookup(row)
        service.release()
        draft = run_async(
            assistant.draft, row.title, row.description, lookup
        )
        reply = service.save_draft(ticket_id, draft)
        return DraftOut(
            reply=ReplyOut.model_validate(reply),
            stop_reason=draft.stop_reason,
            tool_calls=draft.tool_calls,
        )

    @app.post("/replies/{reply_id}/send", tags=["replies"])
    def send_reply(
        reply_id: int,
        service: TicketsDep,
        body: Annotated[ReplyCreate | None, Body()] = None,
    ) -> ReplyOut:
        edited = body.body if body else None
        return ReplyOut.model_validate(service.send_draft(reply_id, edited))

    return app
