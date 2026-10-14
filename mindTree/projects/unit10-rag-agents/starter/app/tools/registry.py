"""Tool registry: Pydantic args -> JSON Schema, validation, authz.

The model PROPOSES a call. This code DECIDES whether it runs:
unknown tool, wrong role, or invalid arguments all come back to the
model as an error result (is_error=True), never as an exception.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent.types import ToolCall, ToolResult, ToolSpec
from app.roles import Principal, Role

log = logging.getLogger(__name__)

# The portable JSON Schema subset we publish to every provider's
# strict mode. Other constraints are enforced by Pydantic and only
# described in text.
SCHEMA_KEYS = {"type", "properties", "required", "enum", "items"}
HINT_KEYS = {
    "pattern": "format {}",
    "minimum": ">= {}",
    "maximum": "<= {}",
    "exclusiveMinimum": "> {}",
    "minLength": "min length {}",
    "maxLength": "max length {}",
}


class ToolError(Exception):
    """Expected failure the model should see (not found, not
    allowed, rule violated)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ToolContext:
    principal: Principal  # from the verified token, never the model
    run_id: str


@dataclass(frozen=True)
class Tool[A: BaseModel]:
    name: str
    description: str
    args_model: type[A]
    handler: Callable[[A, ToolContext], dict[str, object]]
    roles: frozenset[Role]
    side_effect: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(
            self.name, self.description, strict_schema(self.args_model)
        )


def _clean(node: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        k: v for k, v in node.items() if k in SCHEMA_KEYS
    }
    hints = [
        HINT_KEYS[k].format(v) for k, v in node.items() if k in HINT_KEYS
    ]
    desc = str(node.get("description", ""))
    if hints:
        desc = f"{desc} ({', '.join(hints)})".strip()
    if desc:
        out["description"] = desc
    if "properties" in out:
        out["properties"] = {
            name: _clean(prop) for name, prop in out["properties"].items()
        }
        # Strict mode: every property required, nothing extra.
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    if isinstance(out.get("items"), dict):
        out["items"] = _clean(out["items"])
    return out


def strict_schema(model: type[BaseModel]) -> dict[str, object]:
    """Flat Pydantic model -> strict-mode-friendly JSON Schema."""
    schema = model.model_json_schema()
    if "$defs" in schema:
        raise ValueError(f"{model.__name__}: keep tool args flat")
    return _clean(schema)


def _error(
    call: ToolCall, code: str, message: str, **extra: object
) -> ToolResult:
    body = {"error": code, "message": message, **extra}
    return ToolResult(call.id, json.dumps(body), is_error=True)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool[Any]] = {}

    def register(self, tool: Tool[Any]) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool[Any] | None:
        return self._tools.get(name)

    def specs_for(self, role: Role) -> list[ToolSpec]:
        """Least privilege: only show tools this role may call."""
        # TODO(4a): only the specs of tools whose roles include
        # `role`. Right now every role sees every tool.
        return [t.spec() for t in self._tools.values()]

    def execute(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return _error(call, "unknown_tool", f"No tool {call.name}.")
        # TODO(4b): if ctx.principal.role is not in tool.roles,
        # return _error(call, "forbidden", ...) WITHOUT running it.
        try:
            args = tool.args_model.model_validate(call.arguments)
        except ValidationError as exc:
            details = [
                {"field": ".".join(map(str, e["loc"])), "msg": e["msg"]}
                for e in exc.errors()
            ]
            return _error(
                call,
                "invalid_arguments",
                "Fix the arguments and try again.",
                details=details,
            )
        try:
            output = tool.handler(args, ctx)
        except ToolError as exc:
            return _error(call, exc.code, exc.message)
        except Exception:
            log.exception("tool %s crashed", call.name)
            return _error(call, "internal_error", "Tool failed.")
        return ToolResult(call.id, json.dumps(output, sort_keys=True))
