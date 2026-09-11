from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Agent, AgentMessage, Project, Run, Task


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


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[Agent]:
        result = await self._session.execute(select(Agent).order_by(Agent.name))
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Agent | None:
        result = await self._session.execute(select(Agent).where(Agent.name == name))
        return result.scalar_one_or_none()
