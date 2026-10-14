"""User and token schemas."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    VIEWER = "viewer"
    ADMIN = "admin"


class User(BaseModel):
    username: str
    role: Role


class UserInDB(User):
    password_hash: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
