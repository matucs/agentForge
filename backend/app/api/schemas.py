from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str
    repo_path: str
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    repo_path: str
    description: str | None
    created_at: datetime


class TaskCreate(BaseModel):
    project_id: str
    title: str
    requirement_text: str


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str
    requirement_text: str
    status: str
    risk_level: str | None
    created_at: datetime


class RunCreate(BaseModel):
    task_id: str


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    status: str
    branch_name: str | None
    started_at: datetime | None
    finished_at: datetime | None
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    iteration_count: int
    final_decision: str | None
    created_at: datetime


class AgentMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    from_agent: str
    to_agent: str
    type: str
    payload: dict
    created_at: datetime


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    type: str
    produced_by: str
    content: dict
    created_at: datetime


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    severity: str
    file: str | None
    line: int | None
    finding: str
    reason: str | None
    recommendation: str | None
    resolved: bool
    created_at: datetime


class TestResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    suite: str
    passed: bool
    total: int
    failed: int
    duration_seconds: float
    output: str | None
    created_at: datetime


class SecurityFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    severity: str
    category: str
    file: str | None
    detail: str
    blocking: bool
    created_at: datetime


class VerificationResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    gate: str
    passed: bool
    detail: dict
    created_at: datetime


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    action: str
    risk_level: str
    status: str
    requested_reason: str | None
    decided_by: str | None
    decided_at: datetime | None
    created_at: datetime


class ApprovalDecision(BaseModel):
    decided_by: str = "operator"


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    role: str
    responsibilities: str | None
    allowed_tools: list[str] = Field(default_factory=list)


class NotFoundDetail(BaseModel):
    detail: str
