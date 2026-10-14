"""Adapters translate correctly, verified with stub SDK clients.

No network: each stub records the kwargs it received and returns an
object shaped like the real SDK response.
"""

from types import SimpleNamespace as NS
from typing import Any

import anthropic
import httpx
import openai
import pytest

from app.ai.assistant import TOOLS
from app.ai.llm import (
    AnthropicLLM,
    LLMRateLimited,
    LLMTimeout,
    OpenAILLM,
    ToolCall,
)
from app.schemas import TriageResult

RESULT = TriageResult(
    category="billing", priority="high", summary="s", confidence=0.9
)
REQUEST = httpx.Request("POST", "https://api.example/v1")


class Recorder:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.kwargs: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.kwargs.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def anthropic_client(**methods: Recorder) -> Any:
    return NS(messages=NS(**methods))


async def test_anthropic_structured_request_and_usage() -> None:
    parse = Recorder(
        NS(
            parsed_output=RESULT,
            stop_reason="end_turn",
            usage=NS(input_tokens=120, output_tokens=30),
        )
    )
    llm = AnthropicLLM(anthropic_client(parse=parse), "claude-opus-5-5")
    out = await llm.structured("sys", "<ticket>x</ticket>", TriageResult)
    sent = parse.kwargs[0]
    assert sent["model"] == "claude-opus-5-5"
    assert sent["system"] == "sys"  # top-level system parameter
    assert sent["messages"] == [
        {"role": "user", "content": "<ticket>x</ticket>"}
    ]
    assert sent["output_format"] is TriageResult
    assert out.value == RESULT
    assert (out.usage.input_tokens, out.usage.output_tokens) == (120, 30)


async def test_anthropic_tool_loop_wire_format() -> None:
    tool_use = NS(
        type="tool_use",
        id="tu_1",
        name="search_kb",
        input={"query": "late"},
    )
    create = Recorder(
        NS(content=[tool_use], usage=NS(input_tokens=1, output_tokens=1)),
        NS(
            content=[NS(type="text", text="Done [a#1]")],
            usage=NS(input_tokens=1, output_tokens=1),
        ),
    )
    chat = AnthropicLLM(anthropic_client(create=create), "m").chat(
        "sys", "hi"
    )
    turn = await chat.step(TOOLS)
    assert turn.tool_calls == [
        ToolCall("tu_1", "search_kb", {"query": "late"})
    ]
    tools = create.kwargs[0]["tools"]
    assert tools[0]["input_schema"]["required"] == ["query"]
    assert tools[0]["strict"] is True
    chat.add_tool_results([(turn.tool_calls[0], '["ok"]')])
    final = await chat.step(TOOLS)
    assert final.text == "Done [a#1]"
    history = create.kwargs[1]["messages"]
    assert history[1] == {"role": "assistant", "content": [tool_use]}
    assert history[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "tu_1",
        "content": '["ok"]',
    }


async def test_anthropic_errors_are_mapped() -> None:
    rate = anthropic.RateLimitError(
        "slow down",
        response=httpx.Response(429, request=REQUEST),
        body=None,
    )
    llm = AnthropicLLM(anthropic_client(parse=Recorder(rate)), "m")
    with pytest.raises(LLMRateLimited):
        await llm.structured("s", "u", TriageResult)
    timeout = anthropic.APITimeoutError(request=REQUEST)
    llm = AnthropicLLM(anthropic_client(parse=Recorder(timeout)), "m")
    with pytest.raises(LLMTimeout):
        await llm.structured("s", "u", TriageResult)


def openai_client(**methods: Recorder) -> Any:
    return NS(responses=NS(**methods))


async def test_openai_structured_request_and_usage() -> None:
    parse = Recorder(
        NS(output_parsed=RESULT, usage=NS(input_tokens=5, output_tokens=6))
    )
    llm = OpenAILLM(openai_client(parse=parse), "my-model")
    out = await llm.structured("sys", "user text", TriageResult)
    sent = parse.kwargs[0]
    assert sent["instructions"] == "sys"  # Responses API system text
    assert sent["input"] == "user text"
    assert sent["text_format"] is TriageResult
    assert out.usage.output_tokens == 6


async def test_openai_function_call_round_trip() -> None:
    call = NS(
        type="function_call",
        call_id="call_1",
        name="get_order",
        arguments='{"order_id": "ORD-1"}',
    )
    create = Recorder(
        NS(output=[call], output_text="", usage=None),
        NS(output=[], output_text="All done", usage=None),
    )
    chat = OpenAILLM(openai_client(create=create), "m").chat("sys", "hi")
    turn = await chat.step(TOOLS)
    assert turn.tool_calls == [
        ToolCall("call_1", "get_order", {"order_id": "ORD-1"})
    ]
    assert create.kwargs[0]["tools"][1]["type"] == "function"
    chat.add_tool_results([(turn.tool_calls[0], '{"status": "x"}')])
    assert (await chat.step(TOOLS)).text == "All done"
    items = create.kwargs[1]["input"]
    assert items[1] is call  # model output goes back as input
    assert items[2] == {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": '{"status": "x"}',
    }


async def test_openai_requires_model_and_maps_timeout() -> None:
    with pytest.raises(ValueError):
        OpenAILLM(openai_client(), "")
    timeout = openai.APITimeoutError(request=REQUEST)
    llm = OpenAILLM(openai_client(parse=Recorder(timeout)), "m")
    with pytest.raises(LLMTimeout):
        await llm.structured("s", "u", TriageResult)
