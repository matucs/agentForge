"""Structured output contracts for the Planner/Architect/Researcher agents.

Each agent is instructed to return JSON matching one of these models; the
node parses the LLM's text with `Model.model_validate_json` rather than
trusting free-form prose. An LLM response that doesn't match the schema is a
parse failure, not a plan — see app/agents/planner.py etc. for the
retry-then-raise behavior.
"""

from pydantic import BaseModel, Field


class PlannerOutput(BaseModel):
    requirements: list[str] = Field(default_factory=list)
    subtasks: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class ArchitectOutput(BaseModel):
    proposed_components: list[str] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    # Non-empty when the Architect disagrees with something in the
    # Planner's output (spec §5.2: "should challenge the Planner when
    # necessary") — real disagreement the LLM is asked to surface, not a
    # rubber stamp.
    challenges: list[str] = Field(default_factory=list)


class ResearchFinding(BaseModel):
    summary: str
    file_path: str
    evidence_quote: str


class ResearchOutput(BaseModel):
    findings: list[ResearchFinding] = Field(default_factory=list)


class DeveloperFile(BaseModel):
    path: str
    content: str


class DeveloperOutput(BaseModel):
    # Full-file-content replacement, not a diff/patch — a deliberate Phase 5
    # scope line (see docs/limitations.md): simpler to apply deterministically
    # and to unit-test independent of the LLM call.
    files: list[DeveloperFile] = Field(default_factory=list)
    test_files: list[DeveloperFile] = Field(default_factory=list)
    summary: str = ""


class ReviewFinding(BaseModel):
    severity: str  # "low" | "medium" | "high"
    file: str
    line: int | None = None
    finding: str
    reason: str
    recommendation: str


class ReviewOutput(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)
