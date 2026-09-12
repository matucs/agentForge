"""Evaluation results (spec §14/§32). Aggregates are computed live from
real `EvaluationRun` rows — an evaluation nobody has run yet (no
`make eval` executed in this environment) correctly shows zero runs, not a
placeholder.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import EvaluationOut, EvaluationRunOut
from app.db.models import Evaluation, EvaluationRun
from app.db.repositories import EvaluationRepository, EvaluationRunRepository
from app.db.session import get_session

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def _to_evaluation_out(evaluation: Evaluation, runs: list[EvaluationRun]) -> EvaluationOut:
    run_count = len(runs)
    success_count = sum(1 for r in runs if r.success)
    avg_duration = sum(r.duration_seconds for r in runs) / run_count if run_count else None
    avg_cost = sum(r.estimated_cost_usd for r in runs) / run_count if run_count else None
    return EvaluationOut(
        id=evaluation.id,
        name=evaluation.name,
        task_file=evaluation.task_file,
        description=evaluation.description,
        created_at=evaluation.created_at,
        run_count=run_count,
        success_count=success_count,
        avg_duration_seconds=avg_duration,
        avg_estimated_cost_usd=avg_cost,
    )


@router.get("", response_model=list[EvaluationOut])
async def list_evaluations(session: AsyncSession = Depends(get_session)) -> list[EvaluationOut]:
    eval_repo = EvaluationRepository(session)
    run_repo = EvaluationRunRepository(session)
    evaluations = await eval_repo.list()
    result = []
    for evaluation in evaluations:
        runs = await run_repo.list_by_evaluation(evaluation.id)
        result.append(_to_evaluation_out(evaluation, runs))
    return result


@router.get("/{evaluation_id}/runs", response_model=list[EvaluationRunOut])
async def list_evaluation_runs(
    evaluation_id: str, session: AsyncSession = Depends(get_session)
) -> list[EvaluationRunOut]:
    evaluation = await EvaluationRepository(session).get(evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
    runs = await EvaluationRunRepository(session).list_by_evaluation(evaluation_id)
    return [EvaluationRunOut.model_validate(r) for r in runs]
