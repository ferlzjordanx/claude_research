"""Password hashing and JWT handling."""

from __future__ import annotations

import jwt  # noqa: F401  (you will need it)
from pwdlib import PasswordHash

from app.config import Settings
from app.models.user import Role, User  # noqa: F401

# Argon2id via pwdlib: the hashing approach the FastAPI docs now show.
password_hasher = PasswordHash.recommended()


class InvalidTokenError(Exception):
    """Token missing, expired, tampered with, or for another audience."""


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user: User, settings: Settings) -> str:
    """Return a signed JWT for ``user``.

    TODO: implement with jwt.encode(...). Include the claims
    sub, role, iss, aud, iat and exp (now + access_token_minutes) and
    sign with settings.jwt_secret using settings.jwt_algorithm.
    """
    raise NotImplementedError


def decode_access_token(token: str, settings: Settings) -> User:
    """Validate ``token`` and return the User it represents.

    TODO: implement with jwt.decode(...):
      - pin algorithms=[settings.jwt_algorithm]
      - verify audience and issuer
      - require exp, sub, aud, iss
      - convert any jwt.PyJWTError / KeyError / ValueError into
        InvalidTokenError (use `raise ... from exc`)
    """
    raise NotImplementedError
