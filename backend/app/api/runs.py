from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AgentMessageOut,
    ArtifactOut,
    ReviewOut,
    RunCreate,
    RunOut,
    SecurityFindingOut,
    TestResultOut,
)
from app.db.repositories import (
    AgentMessageRepository,
    ArtifactRepository,
    ReviewRepository,
    RunRepository,
    SecurityFindingRepository,
    TaskRepository,
    TestResultRepository,
)
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


@router.get("/{run_id}/artifacts", response_model=list[ArtifactOut])
async def list_run_artifacts(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> list[ArtifactOut]:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    artifacts = await ArtifactRepository(session).list_by_run(run_id)
    return [ArtifactOut.model_validate(a) for a in artifacts]


@router.get("/{run_id}/reviews", response_model=list[ReviewOut])
async def list_run_reviews(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> list[ReviewOut]:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    reviews = await ReviewRepository(session).list_by_run(run_id)
    return [ReviewOut.model_validate(r) for r in reviews]


@router.get("/{run_id}/test-results", response_model=list[TestResultOut])
async def list_run_test_results(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> list[TestResultOut]:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    results = await TestResultRepository(session).list_by_run(run_id)
    return [TestResultOut.model_validate(r) for r in results]


@router.get("/{run_id}/security-findings", response_model=list[SecurityFindingOut])
async def list_run_security_findings(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> list[SecurityFindingOut]:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    findings = await SecurityFindingRepository(session).list_by_run(run_id)
    return [SecurityFindingOut.model_validate(f) for f in findings]


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
