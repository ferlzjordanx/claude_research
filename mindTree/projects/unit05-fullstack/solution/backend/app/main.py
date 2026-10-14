"""Support Desk API. Run: uvicorn app.main:create_app --factory --reload"""

# No `from __future__ import annotations` here: FastAPI must resolve the
# Annotated dependency aliases defined inside create_app at runtime.

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db import Base, UserRow, make_engine, session_scope
from app.errors import register_error_handlers
from app.observability import RequestIdMiddleware, configure_logging
from app.schemas import (
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


def seed_users(factory: sessionmaker[Session], spec: str) -> None:
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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        Base.metadata.create_all(engine)  # dev/demo; prod uses Alembic
        factory = sessionmaker(engine, expire_on_commit=False)
        if settings.env != "prod":
            seed_users(factory, settings.demo_users)
        app.state.session_factory = factory
        yield
        engine.dispose()

    app = FastAPI(
        title="Support Desk API", version="1.0.0", lifespan=lifespan
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
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

    @app.get("/health", tags=["ops"])
    def health(session: SessionDep) -> dict[str, str]:
        session.execute(text("SELECT 1"))
        return {"status": "ok"}

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

    @app.get("/tickets", tags=["tickets"])
    def list_tickets(
        service: TicketsDep,
        status_: Annotated[
            TicketStatus | None, Query(alias="status")
        ] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> TicketPage:
        rows, total = service.list(status_, limit, offset)
        return TicketPage(
            items=[TicketOut.model_validate(r) for r in rows], total=total
        )

    @app.post(
        "/tickets", status_code=status.HTTP_201_CREATED, tags=["tickets"]
    )
    def create_ticket(body: TicketCreate, service: TicketsDep) -> TicketOut:
        return TicketOut.model_validate(service.create(body))

    @app.get("/tickets/{ticket_id}", tags=["tickets"])
    def get_ticket(ticket_id: int, service: TicketsDep) -> TicketOut:
        return TicketOut.model_validate(service.get(ticket_id))

    @app.patch("/tickets/{ticket_id}", tags=["tickets"])
    def update_ticket(
        ticket_id: int, body: TicketStatusUpdate, service: TicketsDep
    ) -> TicketOut:
        return TicketOut.model_validate(
            service.update_status(ticket_id, body.status)
        )

    return app
