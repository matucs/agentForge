from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import TaskCreate, TaskOut
from app.db.repositories import ProjectRepository, TaskRepository
from app.db.session import get_session

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    payload: TaskCreate, session: AsyncSession = Depends(get_session)
) -> TaskOut:
    project = await ProjectRepository(session).get(payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail=f"Project {payload.project_id} not found"
        )

    task = await TaskRepository(session).create(
        project_id=payload.project_id,
        title=payload.title,
        requirement_text=payload.requirement_text,
    )
    return TaskOut.model_validate(task)


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    project_id: str | None = None, session: AsyncSession = Depends(get_session)
) -> list[TaskOut]:
    tasks = await TaskRepository(session).list(project_id=project_id)
    return [TaskOut.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)) -> TaskOut:
    task = await TaskRepository(session).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskOut.model_validate(task)
