"""API schemas (separate from ORM models)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: EmailStr


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sku: str
    name: str
    price: Decimal
    stock: int


class OrderLineIn(BaseModel):
    sku: Annotated[str, Field(min_length=1, max_length=40)]
    quantity: Annotated[int, Field(ge=1, le=1000)]


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: int
    lines: Annotated[list[OrderLineIn], Field(min_length=1, max_length=50)]


class OrderLineOut(BaseModel):
    sku: str
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    id: int
    customer_id: int
    status: str
    total: Decimal
    created_at: datetime
    lines: list[OrderLineOut]
