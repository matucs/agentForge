import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ProjectRepository, RunRepository, TaskRepository
from app.orchestration.errors import check_budget_exceeded


def test_check_budget_exceeded_true_when_over() -> None:
    assert check_budget_exceeded(2.01, 2.00) is True


def test_check_budget_exceeded_false_when_under_or_equal() -> None:
    assert check_budget_exceeded(2.00, 2.00) is False
    assert check_budget_exceeded(1.00, 2.00) is False


@pytest.mark.asyncio
async def test_increment_usage_adds_to_existing_totals_not_overwrites(
    db_session: AsyncSession,
) -> None:
    project = await ProjectRepository(db_session).create(
        name="P", repo_path="/repo", description=None
    )
    task = await TaskRepository(db_session).create(
        project_id=project.id, title="t", requirement_text="r"
    )
    run_repo = RunRepository(db_session)
    run = await run_repo.create(task_id=task.id)

    await run_repo.increment_usage(run.id, input_tokens=100, output_tokens=50, cost_usd=0.01)
    await run_repo.increment_usage(run.id, input_tokens=20, output_tokens=10, cost_usd=0.002)

    updated = await run_repo.get(run.id)
    assert updated is not None
    assert updated.total_input_tokens == 120
    assert updated.total_output_tokens == 60
    assert updated.estimated_cost_usd == pytest.approx(0.012)


@pytest.mark.asyncio
async def test_increment_usage_returns_none_for_unknown_run(db_session: AsyncSession) -> None:
    result = await RunRepository(db_session).increment_usage(
        "does-not-exist", input_tokens=1, output_tokens=1, cost_usd=0.01
    )
    assert result is None
