"""Wire-format tests against the INSTALLED SDK types, no network.

Requests are validated with pydantic TypeAdapter over the SDK's own
TypedDicts; responses are built with the SDK's own response models.
"""

import json
from typing import Any

import pytest
from anthropic.types import (
    Message as AnthropicMessage,
)
from anthropic.types import (
    TextBlockParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
)
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    Response,
    ResponseFunctionToolCallParam,
)
from openai.types.responses.response_input_item_param import (
    FunctionCallOutput,
)
from pydantic import TypeAdapter

from app.agent.anthropic_llm import (
    AnthropicToolLLM,
    from_anthropic_response,
    to_anthropic_messages,
    to_anthropic_tools,
)
from app.agent.loop import Agent, StopReason
from app.agent.openai_llm import (
    OpenAIToolLLM,
    from_openai_response,
    to_openai_input,
    to_openai_tools,
)
from app.agent.types import (
    AssistantMessage,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    UserMessage,
)
from app.roles import Role
from app.tools.registry import ToolRegistry
from tests.conftest import ALICE, ctx

ANSWER = "Original payment method [refund-policy#1]."
CALL = ToolCall("id_1", "search_kb", {"query": "refund", "k": 2})
HISTORY = [
    UserMessage("Where do refunds go?"),
    AssistantMessage("Let me check.", (CALL,)),
    ToolResultsMessage((ToolResult("id_1", '{"results": []}', True),)),
]


def anthropic_message(content: list[dict[str, Any]], stop: str):
    return AnthropicMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }
    )


def openai_response(output: list[dict[str, Any]], status="completed"):
    return Response.model_validate(
        {
            "id": "resp_1",
            "object": "response",
            "created_at": 0,
            "model": "placeholder-model",
            "output": output,
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "status": status,
            "usage": {
                "input_tokens": 5,
                "output_tokens": 3,
                "total_tokens": 8,
                "input_tokens_details": {
                    "cached_tokens": 0,
                    "cache_write_tokens": 0,
                },
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }
    )


def text_item(text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [
            {"type": "output_text", "text": text, "annotations": []}
        ],
    }


class Stub:
    """Mimics client.messages.create / client.responses.create."""

    def __init__(self, replies: list[Any]) -> None:
        self.replies = replies
        self.calls: list[dict[str, Any]] = []
        self.messages = self
        self.responses = self

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.replies.pop(0)


# -- Anthropic --------------------------------------------------------
def test_anthropic_tools_match_sdk_tool_param(
    registry: ToolRegistry,
) -> None:
    for tool in to_anthropic_tools(registry.specs_for(Role.AGENT)):
        TypeAdapter(ToolParam).validate_python(tool)
        assert tool["strict"] is True
        assert tool["input_schema"]["additionalProperties"] is False


def test_anthropic_messages_use_tool_use_and_tool_result_blocks() -> None:
    user, assistant, results = to_anthropic_messages(HISTORY)
    assert user == {"role": "user", "content": "Where do refunds go?"}
    text_block, use_block = assistant["content"]
    TypeAdapter(TextBlockParam).validate_python(text_block)
    TypeAdapter(ToolUseBlockParam).validate_python(use_block)
    assert use_block["input"] == {"query": "refund", "k": 2}
    assert results["role"] == "user"  # results travel as a user turn
    [block] = results["content"]
    TypeAdapter(ToolResultBlockParam).validate_python(block)
    assert block["tool_use_id"] == "id_1" and block["is_error"] is True


def test_anthropic_response_becomes_neutral_tool_calls() -> None:
    message = anthropic_message(
        [
            {"type": "text", "text": "Searching."},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "search_kb",
                "input": {"query": "refund", "k": 2},
            },
        ],
        "tool_use",
    )
    response = from_anthropic_response(message)
    assert response.stop == "tool_use" and response.text == "Searching."
    assert response.tool_calls == (
        ToolCall("toolu_1", "search_kb", {"query": "refund", "k": 2}),
    )
    assert (response.input_tokens, response.output_tokens) == (11, 7)


@pytest.mark.parametrize(
    ("raw", "neutral"),
    [
        ("end_turn", "end"),
        ("max_tokens", "max_tokens"),
        ("refusal", "refusal"),
    ],
)
def test_anthropic_stop_reasons(raw: str, neutral: str) -> None:
    message = anthropic_message([{"type": "text", "text": "x"}], raw)
    assert from_anthropic_response(message).stop == neutral


def test_agent_loop_over_anthropic_stub(registry: ToolRegistry) -> None:
    stub = Stub(
        [
            anthropic_message(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "search_kb",
                        "input": {"query": "Where do refunds go", "k": 2},
                    }
                ],
                "tool_use",
            ),
            anthropic_message(
                [
                    {
                        "type": "text",
                        "text": ANSWER,
                    }
                ],
                "end_turn",
            ),
        ]
    )
    result = Agent(AnthropicToolLLM(stub), registry).run(
        "Where do refunds go?", ctx(ALICE)
    )
    assert result.stop_reason is StopReason.FINAL_ANSWER
    assert result.citation_problems == []
    first, second = stub.calls
    assert first["model"] == "claude-opus-5-5"
    assert "system" in first and first["tools"]
    last = second["messages"][-1]["content"][0]
    assert last["type"] == "tool_result"
    assert last["tool_use_id"] == "toolu_1"


# -- OpenAI -----------------------------------------------------------
def test_openai_tools_match_sdk_function_tool_param(
    registry: ToolRegistry,
) -> None:
    for tool in to_openai_tools(registry.specs_for(Role.AGENT)):
        TypeAdapter(FunctionToolParam).validate_python(tool)
        assert tool["type"] == "function" and tool["strict"] is True


def test_openai_input_items_match_sdk_types() -> None:
    user, text, fn_call, fn_output = to_openai_input(HISTORY)
    TypeAdapter(EasyInputMessageParam).validate_python(user)
    TypeAdapter(EasyInputMessageParam).validate_python(text)
    TypeAdapter(ResponseFunctionToolCallParam).validate_python(fn_call)
    TypeAdapter(FunctionCallOutput).validate_python(fn_output)
    assert json.loads(fn_call["arguments"]) == CALL.arguments
    assert fn_output == {
        "type": "function_call_output",
        "call_id": "id_1",
        "output": '{"results": []}',
    }


def test_openai_response_becomes_neutral_tool_calls() -> None:
    response = from_openai_response(
        openai_response(
            [
                {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_9",
                    "name": "get_order",
                    "arguments": '{"order_id": "ORD-1001"}',
                    "status": "completed",
                }
            ]
        )
    )
    assert response.stop == "tool_use"
    assert response.tool_calls == (
        ToolCall("call_9", "get_order", {"order_id": "ORD-1001"}),
    )
    final = from_openai_response(openai_response([text_item("Done.")]))
    assert (final.stop, final.text) == ("end", "Done.")
    cut = from_openai_response(openai_response([], "incomplete"))
    assert cut.stop == "max_tokens"


def test_openai_bad_json_arguments_become_a_tool_error(
    registry: ToolRegistry,
) -> None:
    response = from_openai_response(
        openai_response(
            [
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "get_order",
                    "arguments": "{oops",
                }
            ]
        )
    )
    [bad] = response.tool_calls
    result = registry.execute(bad, ctx(ALICE))
    assert result.is_error and "invalid_arguments" in result.content


def test_openai_model_is_required() -> None:
    with pytest.raises(ValueError, match="APP_OPENAI_MODEL"):
        OpenAIToolLLM(Stub([]), model="")


def test_agent_loop_over_openai_stub(registry: ToolRegistry) -> None:
    stub = Stub(
        [
            openai_response(
                [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "search_kb",
                        "arguments": '{"query": "Where do refunds go", '
                        '"k": 2}',
                    }
                ]
            ),
            openai_response([text_item(ANSWER)]),
        ]
    )
    llm = OpenAIToolLLM(stub, model="placeholder-model")
    result = Agent(llm, registry).run("Where do refunds go?", ctx(ALICE))
    assert result.stop_reason is StopReason.FINAL_ANSWER
    first, second = stub.calls
    assert first["model"] == "placeholder-model"
    assert first["instructions"] and first["tools"]
    kinds = [item.get("type") for item in second["input"]]
    assert kinds[-2:] == ["function_call", "function_call_output"]
