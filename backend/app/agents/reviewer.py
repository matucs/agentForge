"""Reviewer agent (spec §5.5): inspects the actual diff and produces
structured findings. Its output is one more input to the deterministic
routing/verification layer (ADR-003) — not a final approval."""

from app.agents.llm_json import complete_structured
from app.agents.schemas import ReviewOutput
from app.llm.base import LLMUsage
from app.llm.factory import get_default_provider

_SYSTEM = """You are the Reviewer agent in an autonomous software \
engineering system. You are given a requirement and the actual unified \
diff of a proposed change. Inspect it for real bugs, missing error \
handling, missing tests, security concerns, and architectural problems — \
do not simply approve it. Severity must be "high" (blocks merge — a real \
bug or missing critical behavior), "medium" (should be fixed but not \
blocking), or "low" (nitpick). If the diff genuinely has no issues, return \
an empty findings list rather than inventing one. Respond with ONLY a JSON \
object matching this schema, no markdown fences, no prose:
{
  "findings": [
    {"severity": "high|medium|low", "file": "path", "line": <int or null>, \
"finding": "...", "reason": "...", "recommendation": "..."}
  ]
}"""


async def run_reviewer(requirement_text: str, diff: str) -> tuple[ReviewOutput, LLMUsage]:
    provider = get_default_provider()
    prompt = f"Requirement:\n{requirement_text}\n\nDiff:\n{diff}"
    return await complete_structured(
        provider, system=_SYSTEM, prompt=prompt, output_model=ReviewOutput, max_tokens=4096
    )
