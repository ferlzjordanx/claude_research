from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    quantity: int = Field(default=0, ge=0)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    quantity: int


class VersionOut(BaseModel):
    version: str
    git_sha: str
    environment: str
