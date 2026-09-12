"""Planner agent (spec §5.1): interprets the requirement and produces a
structured implementation plan. Real LLM call via the provider abstraction
— no fallback content on failure, see app/agents/llm_json.py."""

from app.agents.llm_json import complete_structured
from app.agents.schemas import PlannerOutput
from app.llm.base import LLMUsage
from app.llm.factory import get_default_provider

_SYSTEM = """You are the Planner agent in an autonomous software engineering \
system. Given a feature/bug requirement, produce a structured implementation \
plan. Identify ambiguities as risks rather than guessing silently. Respond \
with ONLY a JSON object matching this schema, no markdown fences, no prose:
{
  "requirements": ["..."],
  "subtasks": ["..."],
  "acceptance_criteria": ["..."],
  "risks": ["..."],
  "dependencies": ["..."]
}"""


async def run_planner(requirement_text: str) -> tuple[PlannerOutput, LLMUsage]:
    provider = get_default_provider()
    prompt = f"Requirement:\n{requirement_text}"
    return await complete_structured(
        provider, system=_SYSTEM, prompt=prompt, output_model=PlannerOutput
    )
