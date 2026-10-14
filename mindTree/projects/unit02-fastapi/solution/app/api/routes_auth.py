"""Token endpoint (OAuth2 password flow, for the demo only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import SettingsDep, get_user_repo
from app.core.security import create_access_token, verify_password
from app.models.user import Token, User
from app.repositories.user_repo import InMemoryUserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    users: Annotated[InMemoryUserRepository, Depends(get_user_repo)],
    settings: SettingsDep,
) -> Token:
    # `def`, not `async def`: Argon2 is CPU-heavy, so FastAPI runs this
    # in its threadpool instead of blocking the event loop.
    user = users.get(form.username)
    if user is None or not verify_password(
        form.password, user.password_hash
    ):
        # Same message for unknown user and wrong password (no user
        # enumeration).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    public = User(username=user.username, role=user.role)
    return Token(
        access_token=create_access_token(public, settings),
        expires_in=settings.access_token_minutes * 60,
    )
