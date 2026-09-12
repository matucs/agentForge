"""Shared "call the LLM, parse structured JSON" helper for agents.

One retry on a parse/validation failure (the model sometimes wraps JSON in
prose or markdown fences); a second failure raises rather than falling back
to any default content — an agent that can't produce a valid structured
output has failed, not silently succeeded with empty data.
"""

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMProvider, LLMUsage

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

T = TypeVar("T", bound=BaseModel)


class AgentOutputParseError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match is None:
            raise
        return json.loads(match.group(0))


async def complete_structured(
    provider: LLMProvider,
    *,
    system: str,
    prompt: str,
    output_model: type[T],
    max_tokens: int = 2048,
) -> tuple[T, LLMUsage]:
    """Returns (parsed output, usage). Usage is accumulated across every
    attempt (including a failed parse that still cost real tokens) so a
    caller's cost/budget tracking is never short-changed by a retry."""
    last_error: Exception | None = None
    current_prompt = prompt
    total_usage: LLMUsage | None = None

    for _attempt in range(2):
        response = await provider.complete(
            system=system, prompt=current_prompt, max_tokens=max_tokens
        )
        total_usage = _sum_usage(total_usage, response.usage)
        try:
            data = _extract_json(response.text)
            return output_model.model_validate(data), total_usage
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            current_prompt = (
                f"{prompt}\n\nYour previous response could not be parsed as JSON matching "
                f"the required schema. Error: {exc}\n\nRespond with ONLY valid JSON, no "
                "markdown fences, no commentary."
            )

    raise AgentOutputParseError(
        f"{output_model.__name__} could not be parsed after 2 attempts: {last_error}"
    )


def _sum_usage(existing: LLMUsage | None, addition: LLMUsage) -> LLMUsage:
    if existing is None:
        return addition
    return LLMUsage(
        input_tokens=existing.input_tokens + addition.input_tokens,
        output_tokens=existing.output_tokens + addition.output_tokens,
        estimated_cost_usd=existing.estimated_cost_usd + addition.estimated_cost_usd,
    )
