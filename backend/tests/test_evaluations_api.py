import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import EvaluationRepository, EvaluationRunRepository


@pytest.mark.asyncio
async def test_list_evaluations_is_empty_with_no_data(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/evaluations")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_evaluations_reports_real_aggregates(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    evaluation = await EvaluationRepository(db_session).get_or_create(
        name="pagination", task_file="pagination.yaml"
    )
    run_repo = EvaluationRunRepository(db_session)
    await run_repo.create(
        evaluation_id=evaluation.id,
        run_id=None,
        success=True,
        duration_seconds=10.0,
        estimated_cost_usd=0.05,
    )
    await run_repo.create(
        evaluation_id=evaluation.id,
        run_id=None,
        success=False,
        duration_seconds=20.0,
        estimated_cost_usd=0.10,
    )
    await db_session.flush()

    resp = await client.get("/api/evaluations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "pagination"
    assert body[0]["run_count"] == 2
    assert body[0]["success_count"] == 1
    assert body[0]["avg_duration_seconds"] == 15.0
    assert body[0]["avg_estimated_cost_usd"] == pytest.approx(0.075)


@pytest.mark.asyncio
async def test_list_evaluation_runs_returns_the_real_rows(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    evaluation = await EvaluationRepository(db_session).get_or_create(
        name="authentication", task_file="authentication.yaml"
    )
    await EvaluationRunRepository(db_session).create(
        evaluation_id=evaluation.id,
        run_id=None,
        success=True,
        duration_seconds=5.0,
        estimated_cost_usd=0.01,
    )
    await db_session.flush()

    resp = await client.get(f"/api/evaluations/{evaluation.id}/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["success"] is True


@pytest.mark.asyncio
async def test_list_evaluation_runs_404s_for_unknown_evaluation(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.get("/api/evaluations/does-not-exist/runs")
    assert resp.status_code == 404
