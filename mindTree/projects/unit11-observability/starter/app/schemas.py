"""Response models (the API contract)."""

from pydantic import BaseModel


class RevenueRow(BaseModel):
    customer_id: int
    name: str
    order_count: int
    total_cents: int


class FxReport(BaseModel):
    currency: str
    rate: float
    total_cents_usd: int
    total_cents_converted: int
