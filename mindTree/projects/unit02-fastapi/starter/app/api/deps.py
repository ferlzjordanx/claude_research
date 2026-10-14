"""Dependency providers: FastAPI calls these and injects the results."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status  # noqa: F401
from fastapi.security import OAuth2PasswordBearer

from app.config import Settings, get_settings
from app.core.security import (  # noqa: F401
    InvalidTokenError,
    decode_access_token,
)
from app.models.user import Role, User
from app.repositories.customer_repo import CustomerRepository
from app.repositories.user_repo import InMemoryUserRepository
from app.services.customer_service import CustomerService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_customer_repo(request: Request) -> CustomerRepository:
    repo: CustomerRepository = request.app.state.customer_repo
    return repo


def get_user_repo(request: Request) -> InMemoryUserRepository:
    repo: InMemoryUserRepository = request.app.state.user_repo
    return repo


def get_customer_service(
    repo: Annotated[CustomerRepository, Depends(get_customer_repo)],
) -> CustomerService:
    return CustomerService(repo)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], settings: SettingsDep
) -> User:
    """Authentication: WHO is calling? Invalid token -> 401."""
    # TODO: decode the token with decode_access_token(). On
    # InvalidTokenError raise HTTPException(401) with the header
    # WWW-Authenticate: Bearer.
    raise NotImplementedError


ROLE_RANK = {Role.VIEWER: 1, Role.ADMIN: 2}


def require_role(minimum: Role) -> Callable[..., User]:
    """Authorization: MAY this caller do this? Insufficient -> 403."""

    def checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        # TODO: raise HTTPException(403) when the user's rank is below
        # ROLE_RANK[minimum]; otherwise return the user.
        raise NotImplementedError

    return checker


ServiceDep = Annotated[CustomerService, Depends(get_customer_service)]
ViewerDep = Annotated[User, Depends(require_role(Role.VIEWER))]
AdminDep = Annotated[User, Depends(require_role(Role.ADMIN))]
