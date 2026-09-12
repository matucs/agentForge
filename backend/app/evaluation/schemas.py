"""Evaluation task schema (spec §14). Each YAML file under evals/tasks/ is
validated against this on load — a malformed task file is a real, visible
error, not silently skipped.
"""

from pydantic import BaseModel, Field


class EvalTask(BaseModel):
    name: str
    requirement: str
    expected_behavior: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    known_failure_modes: list[str] = Field(default_factory=list)
