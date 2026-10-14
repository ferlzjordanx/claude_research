"""Business rules live here, not in routes and not in the repository."""

from __future__ import annotations

from app.core.errors import ConflictError, NotFoundError  # noqa: F401
from app.models.customer import Customer, CustomerCreate, CustomerUpdate
from app.repositories.customer_repo import CustomerRepository


class CustomerService:
    def __init__(self, repo: CustomerRepository) -> None:
        self._repo = repo

    def create(self, data: CustomerCreate) -> Customer:
        # TODO: lower-case the email, raise ConflictError if a customer
        # with that email exists, otherwise add it via the repository.
        raise NotImplementedError

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
        # TODO:
        # 1. load the customer (self.get raises NotFoundError)
        # 2. changes = data.model_dump(exclude_unset=True)
        # 3. if email changes: lower-case it; ConflictError if another
        #    customer already uses it
        # 4. model_copy(update={**changes, "updated_at": now}) and save
        raise NotImplementedError

    def delete(self, customer_id: int) -> None:
        # TODO: delete via the repository; NotFoundError if nothing
        # was deleted.
        raise NotImplementedError
