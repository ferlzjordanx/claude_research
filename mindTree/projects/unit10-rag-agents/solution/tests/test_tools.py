import json

import pytest

from app.agent.types import ToolCall
from app.roles import Role
from app.tools.registry import ToolError, ToolRegistry, strict_schema
from app.tools.support import RefundArgs, SupportDesk
from tests.conftest import ALICE, BOB, PAT, SAM, ctx


def run(registry: ToolRegistry, who, name: str, **args: object):
    result = registry.execute(ToolCall("c1", name, args), ctx(who))
    return result, json.loads(result.content)


def test_schema_is_strict_and_portable() -> None:
    schema = strict_schema(RefundArgs)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["order_id", "amount_cents", "reason"]
    assert "title" not in schema
    order_id = schema["properties"]["order_id"]  # type: ignore[index]
    assert "pattern" not in order_id  # enforced by Pydantic instead
    assert "format ^ORD-" in order_id["description"]


def test_invalid_arguments_become_a_tool_error(
    registry: ToolRegistry,
) -> None:
    result, body = run(registry, ALICE, "get_order", order_id="1001")
    assert result.is_error and body["error"] == "invalid_arguments"
    assert body["details"][0]["field"] == "order_id"


def test_extra_arguments_are_rejected(registry: ToolRegistry) -> None:
    _, body = run(
        registry, ALICE, "get_order", order_id="ORD-1001", admin=True
    )
    assert body["error"] == "invalid_arguments"


def test_unknown_tool_is_an_error_not_an_exception(
    registry: ToolRegistry,
) -> None:
    result, body = run(registry, SAM, "delete_database")
    assert result.is_error and body["error"] == "unknown_tool"


def test_customers_do_not_see_or_run_refunds(
    registry: ToolRegistry, desk: SupportDesk
) -> None:
    names = [s.name for s in registry.specs_for(Role.CUSTOMER)]
    assert "issue_refund" not in names
    result, body = run(
        registry,
        ALICE,
        "issue_refund",
        order_id="ORD-1001",
        amount_cents=1000,
        reason="I want it",
    )
    assert result.is_error and body["error"] == "forbidden"
    assert desk.refunds == {}


def test_customers_only_see_their_own_orders(
    registry: ToolRegistry,
) -> None:
    _, own = run(registry, ALICE, "get_order", order_id="ORD-1001")
    assert own["total_cents"] == 12_000
    result, other = run(registry, BOB, "get_order", order_id="ORD-1001")
    assert result.is_error and other["error"] == "not_found"


def test_small_refund_runs_and_is_idempotent(
    registry: ToolRegistry, desk: SupportDesk
) -> None:
    args = {
        "order_id": "ORD-1001",
        "amount_cents": 2000,
        "reason": "Damaged box",
    }
    _, first = run(registry, SAM, "issue_refund", **args)
    _, again = run(registry, SAM, "issue_refund", **args)
    assert first["status"] == "refunded" and not first["replayed"]
    assert again["refund_id"] == first["refund_id"] and again["replayed"]
    assert len(desk.refunds) == 1


def test_large_refund_waits_for_human_approval(
    registry: ToolRegistry, desk: SupportDesk
) -> None:
    _, body = run(
        registry,
        SAM,
        "issue_refund",
        order_id="ORD-1002",
        amount_cents=30_000,
        reason="Arrived broken",
    )
    assert body["status"] == "pending_approval"
    assert desk.refunds == {}  # nothing paid yet
    approval = desk.decide(body["approval_id"], PAT, approve=True)
    twice = desk.decide(body["approval_id"], PAT, approve=True)
    assert approval.status == "approved" and approval.refund_id
    assert twice.refund_id == approval.refund_id
    assert len(desk.refunds) == 1


def test_requester_cannot_approve_own_refund(
    registry: ToolRegistry, desk: SupportDesk
) -> None:
    _, body = run(
        registry,
        SAM,
        "issue_refund",
        order_id="ORD-1002",
        amount_cents=30_000,
        reason="Arrived broken",
    )
    with pytest.raises(ToolError, match="Four-eyes"):
        desk.decide(body["approval_id"], SAM, approve=True)
    with pytest.raises(ToolError):
        desk.decide(body["approval_id"], ALICE, approve=True)


def test_rejected_approval_pays_nothing(
    registry: ToolRegistry, desk: SupportDesk
) -> None:
    _, body = run(
        registry,
        SAM,
        "issue_refund",
        order_id="ORD-1002",
        amount_cents=30_000,
        reason="Arrived broken",
    )
    assert desk.decide(body["approval_id"], PAT, False).status == (
        "rejected"
    )
    assert desk.refunds == {}


@pytest.mark.parametrize(
    ("order_id", "amount", "code"),
    [
        ("ORD-1001", 12_001, "exceeds_order"),
        ("ORD-1004", 100, "fraud_hold"),
        ("ORD-1002", 60_000, "over_limit"),
    ],
)
def test_refund_business_rules(
    retriever, order_id: str, amount: int, code: str
) -> None:
    from app.tools.support import build_registry

    desk = SupportDesk(max_refund_cents=50_000)
    registry = build_registry(retriever, desk, 0.5)
    result, body = run(
        registry,
        SAM,
        "issue_refund",
        order_id=order_id,
        amount_cents=amount,
        reason="Rule check",
    )
    assert result.is_error and body["error"] == code
