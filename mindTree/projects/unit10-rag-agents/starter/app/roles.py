"""Caller identity shared by retrieval, tools and the API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"  # a human support agent using the assistant


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role
