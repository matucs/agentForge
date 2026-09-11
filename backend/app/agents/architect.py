"""Architect agent (spec §5.2): proposes implementation architecture and is
explicitly instructed to challenge the Planner's output when it conflicts
with sound design — not to rubber-stamp it."""

from app.agents.llm_json import complete_structured
from app.agents.schemas import ArchitectOutput, PlannerOutput
from app.llm.factory import get_default_provider

_SYSTEM = """You are the Architect agent in an autonomous software \
engineering system. You are given a requirement and the Planner's proposed \
plan. Propose the implementation architecture: affected components, real \
trade-offs, and risks. If the Planner's plan has a flaw, a missing \
consideration, or conflicts with good design — say so directly in \
"challenges"; do not rubber-stamp a plan you have reservations about. Leave \
"challenges" empty only if you have none. Respond with ONLY a JSON object \
matching this schema, no markdown fences, no prose:
{
  "proposed_components": ["..."],
  "trade_offs": ["..."],
  "risks": ["..."],
  "challenges": ["..."]
}"""


async def run_architect(requirement_text: str, plan: PlannerOutput) -> ArchitectOutput:
    provider = get_default_provider()
    prompt = (
        f"Requirement:\n{requirement_text}\n\n"
        f"Planner's plan (JSON):\n{plan.model_dump_json(indent=2)}"
    )
    return await complete_structured(
        provider, system=_SYSTEM, prompt=prompt, output_model=ArchitectOutput
    )
