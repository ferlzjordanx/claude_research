"""Business rules live here, not in routes and not in the repository."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.errors import ConflictError, NotFoundError
from app.models.customer import Customer, CustomerCreate, CustomerUpdate
from app.repositories.customer_repo import CustomerRepository


class CustomerService:
    def __init__(self, repo: CustomerRepository) -> None:
        self._repo = repo

    def create(self, data: CustomerCreate) -> Customer:
        email = data.email.lower()
        if self._repo.get_by_email(email):
            raise ConflictError(f"A customer with email {email} exists.")
        return self._repo.add(data.name, email, data.company)

    def get(self, customer_id: int) -> Customer:
        customer = self._repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found.")
        return customer

    def list(
        self, *, limit: int, offset: int, query: str | None
    ) -> tuple[list[Customer], int]:
        return self._repo.list(limit=limit, offset=offset, query=query)

    def update(self, customer_id: int, data: CustomerUpdate) -> Customer:
        customer = self.get(customer_id)
        # exclude_unset distinguishes "not sent" from "sent as null".
        changes = data.model_dump(exclude_unset=True)
        if "email" in changes:
            changes["email"] = changes["email"].lower()
            other = self._repo.get_by_email(changes["email"])
            if other and other.id != customer_id:
                raise ConflictError(
                    "Email already used by another customer."
                )
        updated = customer.model_copy(
            update={**changes, "updated_at": datetime.now(UTC)}
        )
        return self._repo.update(updated)

    def delete(self, customer_id: int) -> None:
        if not self._repo.delete(customer_id):
            raise NotFoundError(f"Customer {customer_id} not found.")
