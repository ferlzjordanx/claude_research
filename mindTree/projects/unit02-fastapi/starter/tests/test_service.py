"""Service tests need no HTTP at all: business rules in isolation."""

import pytest
from pydantic import ValidationError

from app.core.errors import ConflictError, NotFoundError
from app.models.customer import CustomerCreate, CustomerUpdate
from app.repositories.customer_repo import InMemoryCustomerRepository
from app.services.customer_service import CustomerService


@pytest.fixture
def service() -> CustomerService:
    return CustomerService(InMemoryCustomerRepository())


def test_email_uniqueness_is_case_insensitive(
    service: CustomerService,
) -> None:
    service.create(CustomerCreate(name="A", email="a@example.com"))
    with pytest.raises(ConflictError):
        service.create(CustomerCreate(name="B", email="A@EXAMPLE.com"))


def test_patch_schema_rejects_explicit_null() -> None:
    with pytest.raises(ValidationError):
        CustomerUpdate(name=None)
    assert CustomerUpdate().model_fields_set == set()  # omitted is fine


def test_missing_customer(service: CustomerService) -> None:
    with pytest.raises(NotFoundError):
        service.get(42)
