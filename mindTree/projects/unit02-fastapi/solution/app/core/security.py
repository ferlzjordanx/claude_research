"""Password hashing and JWT handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import Settings
from app.models.user import Role, User

# Argon2id via pwdlib: the hashing approach the FastAPI docs now show.
password_hasher = PasswordHash.recommended()


class InvalidTokenError(Exception):
    """Token missing, expired, tampered with, or for another audience."""


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": user.username,
        "role": user.role.value,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(
        claims,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> User:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            # Pin the algorithm list: never accept "none" or a different
            # algorithm chosen by whoever crafted the token.
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
        return User(username=claims["sub"], role=Role(claims["role"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
