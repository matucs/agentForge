from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import RunCreate, RunOut
from app.db.repositories import RunRepository, TaskRepository
from app.db.session import get_session

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=201)
async def create_run(payload: RunCreate, session: AsyncSession = Depends(get_session)) -> RunOut:
    task = await TaskRepository(session).get(payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {payload.task_id} not found")

    run = await RunRepository(session).create(task_id=payload.task_id)
    return RunOut.model_validate(run)


@router.get("", response_model=list[RunOut])
async def list_runs(
    task_id: str | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[RunOut]:
    runs = await RunRepository(session).list(task_id=task_id, status=status)
    return [RunOut.model_validate(r) for r in runs]


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)) -> RunOut:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return RunOut.model_validate(run)
