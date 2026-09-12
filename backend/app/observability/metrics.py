"""GET /api/metrics (spec §16/§22): every value below is computed live from
a real DB query at request time — Gauges are `.set()` fresh each scrape,
never a stale in-memory counter that could drift from the actual database
state. No fabricated numbers (spec §35).
"""

from prometheus_client import CollectorRegistry, Gauge, generate_latest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Approval, Run, ToolCall, VerificationResult

_RUN_STATUSES = (
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
    "stopped_by_timeout",
    "stopped_by_budget",
    "blocked",
    "awaiting_approval",
    "rejected",
)


async def render_metrics(session: AsyncSession) -> bytes:
    registry = CollectorRegistry()

    runs_total = Gauge("agentforge_runs_total", "Total runs", registry=registry)
    runs_by_status = Gauge(
        "agentforge_runs_by_status", "Runs by status", ["status"], registry=registry
    )
    verification_failures = Gauge(
        "agentforge_verification_failures_total",
        "Verification gate checks that did not pass",
        registry=registry,
    )
    human_approvals = Gauge(
        "agentforge_human_approvals_total", "Approval rows created", registry=registry
    )
    llm_input_tokens = Gauge(
        "agentforge_llm_input_tokens_total", "Summed real input tokens across runs",
        registry=registry,
    )
    llm_output_tokens = Gauge(
        "agentforge_llm_output_tokens_total", "Summed real output tokens across runs",
        registry=registry,
    )
    estimated_cost = Gauge(
        "agentforge_estimated_llm_cost_usd_total",
        "Summed real estimated LLM cost across runs",
        registry=registry,
    )
    agent_duration = Gauge(
        "agentforge_agent_duration_seconds_avg",
        "Average real duration per agent node execution",
        ["agent"],
        registry=registry,
    )
    agent_errors = Gauge(
        "agentforge_agent_errors_total", "Failed agent node executions", ["agent"],
        registry=registry,
    )

    total = (await session.execute(select(func.count()).select_from(Run))).scalar_one()
    runs_total.set(total)

    for status in _RUN_STATUSES:
        count = (
            await session.execute(
                select(func.count()).select_from(Run).where(Run.status == status)
            )
        ).scalar_one()
        runs_by_status.labels(status=status).set(count)

    verification_failure_count = (
        await session.execute(
            select(func.count())
            .select_from(VerificationResult)
            .where(VerificationResult.passed.is_(False))
        )
    ).scalar_one()
    verification_failures.set(verification_failure_count)

    approval_count = (
        await session.execute(select(func.count()).select_from(Approval))
    ).scalar_one()
    human_approvals.set(approval_count)

    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(Run.total_input_tokens), 0),
                func.coalesce(func.sum(Run.total_output_tokens), 0),
                func.coalesce(func.sum(Run.estimated_cost_usd), 0.0),
            )
        )
    ).one()
    llm_input_tokens.set(totals[0])
    llm_output_tokens.set(totals[1])
    estimated_cost.set(totals[2])

    agent_stats = (
        await session.execute(
            select(
                ToolCall.agent,
                func.avg(ToolCall.duration_seconds),
                func.count().filter(ToolCall.succeeded.is_(False)),
            ).group_by(ToolCall.agent)
        )
    ).all()
    for agent_name, avg_duration, error_count in agent_stats:
        agent_duration.labels(agent=agent_name).set(float(avg_duration or 0.0))
        agent_errors.labels(agent=agent_name).set(error_count)

    return generate_latest(registry)
