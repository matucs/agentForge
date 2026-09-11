from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AgentMessageOut, RunCreate, RunOut
from app.db.repositories import AgentMessageRepository, RunRepository, TaskRepository
from app.db.session import get_session
from app.orchestration.service import (
    RunNotFoundError,
    RunNotPendingError,
    cancel_run,
    start_run,
)

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


@router.get("/{run_id}/events", response_model=list[AgentMessageOut])
async def list_run_events(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> list[AgentMessageOut]:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    messages = await AgentMessageRepository(session).list_by_run(run_id)
    return [AgentMessageOut.model_validate(m) for m in messages]


@router.post("/{run_id}/start", response_model=RunOut, status_code=202)
async def start_run_endpoint(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> RunOut:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    try:
        await start_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunNotPendingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    refreshed = await RunRepository(session).get(run_id)
    assert refreshed is not None
    return RunOut.model_validate(refreshed)


@router.post("/{run_id}/cancel", response_model=RunOut)
async def cancel_run_endpoint(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> RunOut:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    cancelled = cancel_run(run_id)
    if not cancelled:
        raise HTTPException(
            status_code=409, detail=f"Run {run_id} is not currently running in this process"
        )

    refreshed = await RunRepository(session).get(run_id)
    assert refreshed is not None
    return RunOut.model_validate(refreshed)
