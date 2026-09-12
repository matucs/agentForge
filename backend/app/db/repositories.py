from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Agent,
    AgentMessage,
    Approval,
    Artifact,
    Evaluation,
    EvaluationRun,
    Project,
    Review,
    Run,
    SecurityFinding,
    Task,
    TestResult,
    ToolCall,
    VerificationResult,
)


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, name: str, repo_path: str, description: str | None) -> Project:
        project = Project(name=name, repo_path=repo_path, description=description)
        self._session.add(project)
        await self._session.flush()
        return project

    async def get(self, project_id: str) -> Project | None:
        return await self._session.get(Project, project_id)

    async def list(self) -> list[Project]:
        result = await self._session.execute(select(Project).order_by(Project.created_at.desc()))
        return list(result.scalars().all())


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, project_id: str, title: str, requirement_text: str) -> Task:
        task = Task(project_id=project_id, title=title, requirement_text=requirement_text)
        self._session.add(task)
        await self._session.flush()
        return task

    async def get(self, task_id: str) -> Task | None:
        return await self._session.get(Task, task_id)

    async def list(self, *, project_id: str | None = None) -> list[Task]:
        stmt = select(Task).order_by(Task.created_at.desc())
        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, task_id: str) -> Run:
        run = Run(task_id=task_id, status="pending")
        self._session.add(run)
        await self._session.flush()
        return run

    async def get(self, run_id: str) -> Run | None:
        return await self._session.get(Run, run_id)

    async def list(self, *, task_id: str | None = None, status: str | None = None) -> list[Run]:
        stmt = select(Run).order_by(Run.created_at.desc())
        if task_id is not None:
            stmt = stmt.where(Run.task_id == task_id)
        if status is not None:
            stmt = stmt.where(Run.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, run_id: str, **fields: Any) -> Run | None:
        run = await self._session.get(Run, run_id)
        if run is None:
            return None
        for key, value in fields.items():
            setattr(run, key, value)
        await self._session.flush()
        return run

    async def increment_usage(
        self, run_id: str, *, input_tokens: int, output_tokens: int, cost_usd: float
    ) -> Run | None:
        """Adds to the run's existing totals — never overwrites — so usage
        from every agent call in the run accumulates correctly."""
        run = await self._session.get(Run, run_id)
        if run is None:
            return None
        run.total_input_tokens += input_tokens
        run.total_output_tokens += output_tokens
        run.estimated_cost_usd += cost_usd
        await self._session.flush()
        return run


class AgentMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        run_id: str,
        task_id: str,
        from_agent: str,
        to_agent: str,
        type: str,
        payload: dict,
        artifact_id: str | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            run_id=run_id,
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            type=type,
            artifact_id=artifact_id,
            payload=payload,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_by_run(self, run_id: str) -> list[AgentMessage]:
        result = await self._session.execute(
            select(AgentMessage).where(AgentMessage.run_id == run_id).order_by(AgentMessage.seq)
        )
        return list(result.scalars().all())


class ArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, run_id: str, type: str, produced_by: str, content: dict
    ) -> Artifact:
        artifact = Artifact(run_id=run_id, type=type, produced_by=produced_by, content=content)
        self._session.add(artifact)
        await self._session.flush()
        return artifact

    async def list_by_run(self, run_id: str) -> list[Artifact]:
        result = await self._session.execute(
            select(Artifact)
            .where(Artifact.run_id == run_id)
            .order_by(Artifact.created_at, Artifact.id)
        )
        return list(result.scalars().all())


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        run_id: str,
        severity: str,
        file: str | None,
        line: int | None,
        finding: str,
        reason: str | None,
        recommendation: str | None,
    ) -> Review:
        review = Review(
            run_id=run_id,
            severity=severity,
            file=file,
            line=line,
            finding=finding,
            reason=reason,
            recommendation=recommendation,
        )
        self._session.add(review)
        await self._session.flush()
        return review

    async def list_by_run(self, run_id: str) -> list[Review]:
        result = await self._session.execute(
            select(Review).where(Review.run_id == run_id).order_by(Review.created_at, Review.id)
        )
        return list(result.scalars().all())


class TestResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        run_id: str,
        suite: str,
        passed: bool,
        total: int,
        failed: int,
        duration_seconds: float,
        output: str | None,
    ) -> TestResult:
        test_result = TestResult(
            run_id=run_id,
            suite=suite,
            passed=passed,
            total=total,
            failed=failed,
            duration_seconds=duration_seconds,
            output=output,
        )
        self._session.add(test_result)
        await self._session.flush()
        return test_result

    async def list_by_run(self, run_id: str) -> list[TestResult]:
        result = await self._session.execute(
            select(TestResult)
            .where(TestResult.run_id == run_id)
            .order_by(TestResult.created_at, TestResult.id)
        )
        return list(result.scalars().all())


class SecurityFindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        run_id: str,
        severity: str,
        category: str,
        file: str | None,
        detail: str,
        blocking: bool,
    ) -> SecurityFinding:
        finding = SecurityFinding(
            run_id=run_id,
            severity=severity,
            category=category,
            file=file,
            detail=detail,
            blocking=blocking,
        )
        self._session.add(finding)
        await self._session.flush()
        return finding

    async def list_by_run(self, run_id: str) -> list[SecurityFinding]:
        result = await self._session.execute(
            select(SecurityFinding)
            .where(SecurityFinding.run_id == run_id)
            .order_by(SecurityFinding.created_at, SecurityFinding.id)
        )
        return list(result.scalars().all())


class VerificationResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, run_id: str, gate: str, passed: bool, detail: dict
    ) -> VerificationResult:
        result = VerificationResult(run_id=run_id, gate=gate, passed=passed, detail=detail)
        self._session.add(result)
        await self._session.flush()
        return result

    async def list_by_run(self, run_id: str) -> list[VerificationResult]:
        result = await self._session.execute(
            select(VerificationResult)
            .where(VerificationResult.run_id == run_id)
            .order_by(VerificationResult.created_at, VerificationResult.id)
        )
        return list(result.scalars().all())


class ApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        run_id: str,
        action: str,
        risk_level: str,
        requested_reason: str | None = None,
    ) -> Approval:
        approval = Approval(
            run_id=run_id,
            action=action,
            risk_level=risk_level,
            status="pending",
            requested_reason=requested_reason,
        )
        self._session.add(approval)
        await self._session.flush()
        return approval

    async def get(self, approval_id: str) -> Approval | None:
        return await self._session.get(Approval, approval_id)

    async def list(self, *, status: str | None = None) -> list[Approval]:
        stmt = select(Approval).order_by(Approval.created_at.desc())
        if status is not None:
            stmt = stmt.where(Approval.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, approval_id: str, **fields: Any) -> Approval | None:
        approval = await self._session.get(Approval, approval_id)
        if approval is None:
            return None
        for key, value in fields.items():
            setattr(approval, key, value)
        await self._session.flush()
        return approval


class ToolCallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        run_id: str,
        agent: str,
        tool_name: str,
        duration_seconds: float,
        succeeded: bool,
        result_summary: str | None = None,
    ) -> ToolCall:
        tool_call = ToolCall(
            run_id=run_id,
            agent=agent,
            tool_name=tool_name,
            duration_seconds=duration_seconds,
            succeeded=succeeded,
            result_summary=result_summary,
        )
        self._session.add(tool_call)
        await self._session.flush()
        return tool_call

    async def list_by_run(self, run_id: str) -> list[ToolCall]:
        result = await self._session.execute(
            select(ToolCall)
            .where(ToolCall.run_id == run_id)
            .order_by(ToolCall.created_at, ToolCall.id)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[ToolCall]:
        """Used by the metrics endpoint to compute real per-agent
        aggregates across every run — not scoped to one run_id."""
        result = await self._session.execute(select(ToolCall))
        return list(result.scalars().all())


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self, *, name: str, task_file: str, description: str | None = None
    ) -> Evaluation:
        result = await self._session.execute(select(Evaluation).where(Evaluation.name == name))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing
        evaluation = Evaluation(name=name, task_file=task_file, description=description)
        self._session.add(evaluation)
        await self._session.flush()
        return evaluation

    async def list(self) -> list[Evaluation]:
        result = await self._session.execute(select(Evaluation).order_by(Evaluation.name))
        return list(result.scalars().all())

    async def get(self, evaluation_id: str) -> Evaluation | None:
        return await self._session.get(Evaluation, evaluation_id)


class EvaluationRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        evaluation_id: str,
        run_id: str | None,
        success: bool,
        duration_seconds: float,
        estimated_cost_usd: float,
        reviewer_correct: bool | None = None,
        qa_detected: bool | None = None,
        security_detected: bool | None = None,
    ) -> EvaluationRun:
        evaluation_run = EvaluationRun(
            evaluation_id=evaluation_id,
            run_id=run_id,
            success=success,
            duration_seconds=duration_seconds,
            estimated_cost_usd=estimated_cost_usd,
            reviewer_correct=reviewer_correct,
            qa_detected=qa_detected,
            security_detected=security_detected,
        )
        self._session.add(evaluation_run)
        await self._session.flush()
        return evaluation_run

    async def list_by_evaluation(self, evaluation_id: str) -> list[EvaluationRun]:
        result = await self._session.execute(
            select(EvaluationRun).where(EvaluationRun.evaluation_id == evaluation_id)
        )
        return list(result.scalars().all())


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[Agent]:
        result = await self._session.execute(select(Agent).order_by(Agent.name))
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Agent | None:
        result = await self._session.execute(select(Agent).where(Agent.name == name))
        return result.scalar_one_or_none()
