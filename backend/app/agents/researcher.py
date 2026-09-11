"""Researcher agent (spec §5.3): gathers real evidence from the repository
before asking the LLM to reason over it, then discards any LLM "finding"
that cites a file never actually seen. Deterministic retrieval, then LLM
synthesis, then a deterministic grounding check — the same
propose-then-verify shape as the rest of the system, applied one level down.
"""

import re

from app.agents.llm_json import complete_structured
from app.agents.repo_tools import list_files, search_keyword
from app.agents.schemas import ArchitectOutput, PlannerOutput, ResearchFinding, ResearchOutput
from app.llm.factory import get_default_provider

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "when",
    "should",
    "must",
    "will",
    "have",
    "does",
    "add",
    "fix",
}

_SYSTEM = """You are the Researcher agent in an autonomous software \
engineering system. You are given a requirement, the current plan and \
architecture proposal, and a list of files/snippets actually found in the \
repository by a real search — this list is your ONLY source of truth about \
what exists in the codebase. Do not reference any file that is not in the \
provided evidence; if you have no relevant evidence, return an empty \
findings list rather than guessing. Respond with ONLY a JSON object \
matching this schema, no markdown fences, no prose:
{
  "findings": [
    {"summary": "...", "file_path": "<must be one of the listed files>", \
"evidence_quote": "<a short quote from the provided evidence>"}
  ]
}"""


def _extract_keywords(requirement_text: str, max_keywords: int = 5) -> list[str]:
    words = re.findall(r"[a-zA-Z_]{4,}", requirement_text.lower())
    seen: list[str] = []
    for word in words:
        if word not in _STOPWORDS and word not in seen:
            seen.append(word)
        if len(seen) >= max_keywords:
            break
    return seen


def filter_grounded_findings(
    findings: list[ResearchFinding], scanned_files: set[str]
) -> tuple[list[ResearchFinding], list[ResearchFinding]]:
    """Splits findings into (grounded, discarded) — discarded are findings
    citing a file_path that was never actually part of this run's real
    repository scan, i.e. the LLM invented or misremembered it."""
    grounded = [f for f in findings if f.file_path in scanned_files]
    discarded = [f for f in findings if f.file_path not in scanned_files]
    return grounded, discarded


async def run_researcher(
    requirement_text: str,
    repo_path: str,
    plan: PlannerOutput,
    architecture: ArchitectOutput,
) -> tuple[ResearchOutput, list[ResearchFinding]]:
    """Returns (grounded output, discarded findings) — callers should persist
    both so a dropped, ungrounded finding is visible in the artifact, not
    silently swallowed."""
    scanned_files = list_files(repo_path)
    scanned_set = set(scanned_files)

    evidence_lines: list[str] = [f"Files present in repository ({len(scanned_files)}):"]
    evidence_lines.extend(f"- {f}" for f in scanned_files)

    for keyword in _extract_keywords(requirement_text):
        matches = search_keyword(repo_path, keyword)
        if matches:
            evidence_lines.append(f"\nMatches for '{keyword}':")
            evidence_lines.extend(f"- {m.file}:{m.line}: {m.snippet}" for m in matches)

    provider = get_default_provider()
    prompt = (
        f"Requirement:\n{requirement_text}\n\n"
        f"Plan (JSON):\n{plan.model_dump_json()}\n\n"
        f"Architecture (JSON):\n{architecture.model_dump_json()}\n\n"
        f"Repository evidence:\n" + "\n".join(evidence_lines)
    )

    raw_output = await complete_structured(
        provider, system=_SYSTEM, prompt=prompt, output_model=ResearchOutput
    )

    grounded, discarded = filter_grounded_findings(raw_output.findings, scanned_set)
    return ResearchOutput(findings=grounded), discarded
