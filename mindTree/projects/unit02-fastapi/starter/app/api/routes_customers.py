"""Customer resource: thin HTTP layer that delegates to the service."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdminDep, ServiceDep, ViewerDep
from app.models.customer import (
    CustomerCreate,
    CustomerOut,
    CustomerPage,
    CustomerUpdate,  # noqa: F401
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
async def list_customers(
    service: ServiceDep,
    _: ViewerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> CustomerPage:
    items, total = service.list(limit=limit, offset=offset, query=q)
    return CustomerPage(
        items=[
            CustomerOut.model_validate(c, from_attributes=True)
            for c in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    service: ServiceDep,
    _: AdminDep,
    response: Response,
) -> CustomerOut:
    # TODO: create via the service, set the Location header to
    # /customers/{id}, return the CustomerOut.
    raise NotImplementedError


@router.get("/{customer_id}")
async def get_customer(
    customer_id: int, service: ServiceDep, _: ViewerDep
) -> CustomerOut:
    return CustomerOut.model_validate(
        service.get(customer_id), from_attributes=True
    )


# TODO: PATCH /customers/{customer_id} (admin only) -> CustomerOut


# TODO: DELETE /customers/{customer_id} (admin only) -> 204 No Content
