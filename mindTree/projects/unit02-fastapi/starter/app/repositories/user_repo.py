"""Demo user store. Production: an identity provider (Cognito, Entra
ID, Auth0, Okta) issues tokens and this service only validates them."""

from __future__ import annotations

from app.core.security import hash_password
from app.models.user import Role, UserInDB


class InMemoryUserRepository:
    def __init__(self, users: dict[str, UserInDB]) -> None:
        self._users = users

    @classmethod
    def from_spec(cls, spec: str) -> InMemoryUserRepository:
        """Parse 'name:password:role,name2:password2:role2'."""
        users: dict[str, UserInDB] = {}
        for item in filter(None, (s.strip() for s in spec.split(","))):
            username, password, role = item.split(":")
            users[username] = UserInDB(
                username=username,
                role=Role(role),
                password_hash=hash_password(password),
            )
        return cls(users)

    def get(self, username: str) -> UserInDB | None:
        return self._users.get(username)
