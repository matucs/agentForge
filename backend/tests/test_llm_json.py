"""Tests for the complete_structured retry/parse plumbing in
app/agents/llm_json.py. This is infrastructure code (parsing, retrying),
not simulated agent intelligence — the fake provider below stands in for
the network boundary the same way the fake graph in
test_orchestration.py's cancel/timeout tests does, so we can deterministically
exercise a failure path without depending on a real, flaky network call.
"""

import pytest
from pydantic import BaseModel

from app.agents.llm_json import AgentOutputParseError, complete_structured
from app.llm.base import LLMProvider, LLMResponse, LLMUsage


class _ExampleOutput(BaseModel):
    value: str


class _ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    def is_configured(self) -> bool:
        return True

    async def complete(
        self, *, system: str, prompt: str, max_tokens: int = 2048, temperature: float = 0.2
    ) -> LLMResponse:
        text = self._responses[self.call_count]
        self.call_count += 1
        return LLMResponse(
            text=text,
            model="scripted-model",
            provider=self.name,
            usage=LLMUsage(input_tokens=10, output_tokens=5, estimated_cost_usd=0.001),
        )


@pytest.mark.asyncio
async def test_complete_structured_parses_clean_json_on_first_try() -> None:
    provider = _ScriptedProvider(['{"value": "ok"}'])
    result, usage = await complete_structured(
        provider, system="sys", prompt="p", output_model=_ExampleOutput
    )
    assert result.value == "ok"
    assert provider.call_count == 1
    assert usage.input_tokens == 10
    assert usage.output_tokens == 5


@pytest.mark.asyncio
async def test_complete_structured_extracts_json_wrapped_in_prose_or_fences() -> None:
    provider = _ScriptedProvider(['Sure, here is the JSON:\n```json\n{"value": "ok"}\n```\n'])
    result, _usage = await complete_structured(
        provider, system="sys", prompt="p", output_model=_ExampleOutput
    )
    assert result.value == "ok"


@pytest.mark.asyncio
async def test_complete_structured_retries_once_then_succeeds() -> None:
    provider = _ScriptedProvider(["not json at all", '{"value": "recovered"}'])
    result, usage = await complete_structured(
        provider, system="sys", prompt="p", output_model=_ExampleOutput
    )
    assert result.value == "recovered"
    assert provider.call_count == 2
    # Usage from BOTH attempts is accumulated — the failed first attempt
    # still cost real tokens and must not be silently dropped.
    assert usage.input_tokens == 20
    assert usage.output_tokens == 10


@pytest.mark.asyncio
async def test_complete_structured_raises_after_two_failed_attempts() -> None:
    provider = _ScriptedProvider(["still not json", "still not json either"])
    with pytest.raises(AgentOutputParseError):
        await complete_structured(provider, system="sys", prompt="p", output_model=_ExampleOutput)
    assert provider.call_count == 2
