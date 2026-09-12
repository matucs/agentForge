import asyncio
import logging
import time
from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.db.repositories import ProjectRepository, RunRepository, TaskRepository
from app.db.session import async_session_factory
from app.observability.logging import get_logger
from app.observability.tracing import get_tracer
from app.orchestration.errors import BudgetExceededError
from app.orchestration.graph import build_graph, checkpointer_context
from app.orchestration.state import AgentState

logger = logging.getLogger(__name__)
_struct_logger = get_logger(__name__)
_tracer = get_tracer(__name__)

# In-process registry of running orchestration tasks, keyed by run_id, so a
# run can be cancelled via the API. This registry is intentionally not
# durable: if the backend restarts mid-run, the Postgres `runs.status` row
# (left at "running") is the durable record that something was interrupted
# — see docs/limitations.md. It does not silently claim completion.
_running_tasks: dict[str, asyncio.Task] = {}


class RunNotPendingError(RuntimeError):
    pass


class RunNotFoundError(RuntimeError):
    pass


async def _load_initial_state(run_id: str) -> AgentState:
    async with async_session_factory() as session:
        run = await RunRepository(session).get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        task = await TaskRepository(session).get(run.task_id)
        if task is None:
            raise RunNotFoundError(f"task for run {run_id}")
        project = await ProjectRepository(session).get(task.project_id)
        if project is None:
            raise RunNotFoundError(f"project for task {task.id}")

        return AgentState(
            run_id=run_id,
            task_id=task.id,
            requirement_text=task.requirement_text,
            repo_path=project.repo_path,
            plan=None,
            architecture=None,
            research=None,
            review_findings=[],
            test_results=[],
            security_findings=[],
            verification_result=None,
            final_decision=None,
            iteration_count=0,
            status="running",
            error=None,
        )


async def _run_graph(run_id: str) -> None:
    settings = get_settings()
    started_at = time.monotonic()

    async with async_session_factory() as session:
        await RunRepository(session).update(
            run_id, status="running", started_at=datetime.now(UTC)
        )
        await session.commit()

    _struct_logger.info("run_started", run_id=run_id, status="running")

    with _tracer.start_as_current_span("run") as span:
        span.set_attribute("run_id", run_id)
        try:
            initial_state = await _load_initial_state(run_id)

            async with checkpointer_context() as checkpointer:
                graph = build_graph().compile(checkpointer=checkpointer)
                config: RunnableConfig = {"configurable": {"thread_id": run_id}}
                final_state = await asyncio.wait_for(
                    graph.ainvoke(initial_state, config=config),
                    timeout=settings.max_workflow_seconds,
                )

            async with async_session_factory() as session:
                repo = RunRepository(session)
                # policy_node (Phase 6) already sets the real terminal
                # status — "completed", "blocked", or "awaiting_approval" —
                # before the graph reaches END. Only fall back to
                # "completed" here if that never happened (e.g. an older/
                # placeholder policy node), so this never clobbers a real
                # block/approval-pending decision.
                current = await repo.get(run_id)
                status = (
                    current.status if current and current.status != "running" else "completed"
                )
                await repo.update(
                    run_id,
                    status=status,
                    finished_at=datetime.now(UTC),
                    iteration_count=final_state["iteration_count"],
                    final_decision=final_state.get("final_decision"),
                )
                await session.commit()
            _log_run_finished(run_id, status, started_at)

        except TimeoutError:
            async with async_session_factory() as session:
                await RunRepository(session).update(
                    run_id, status="stopped_by_timeout", finished_at=datetime.now(UTC)
                )
                await session.commit()
            _log_run_finished(run_id, "stopped_by_timeout", started_at)

        except BudgetExceededError:
            async with async_session_factory() as session:
                await RunRepository(session).update(
                    run_id, status="stopped_by_budget", finished_at=datetime.now(UTC)
                )
                await session.commit()
            _log_run_finished(run_id, "stopped_by_budget", started_at)

        except asyncio.CancelledError:
            async with async_session_factory() as session:
                await RunRepository(session).update(
                    run_id, status="cancelled", finished_at=datetime.now(UTC)
                )
                await session.commit()
            _log_run_finished(run_id, "cancelled", started_at)
            raise

        except Exception:
            logger.exception("Run %s failed", run_id)
            async with async_session_factory() as session:
                await RunRepository(session).update(
                    run_id, status="failed", finished_at=datetime.now(UTC)
                )
                await session.commit()
            _log_run_finished(run_id, "failed", started_at)

        finally:
            _running_tasks.pop(run_id, None)


def _log_run_finished(run_id: str, status: str, started_at: float) -> None:
    _struct_logger.info(
        "run_finished",
        run_id=run_id,
        status=status,
        duration=round(time.monotonic() - started_at, 4),
    )


async def start_run(run_id: str) -> None:
    async with async_session_factory() as session:
        run = await RunRepository(session).get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        if run.status != "pending":
            raise RunNotPendingError(f"run {run_id} is {run.status}, not pending")

    task = asyncio.create_task(_run_graph(run_id))
    _running_tasks[run_id] = task


def cancel_run(run_id: str) -> bool:
    task = _running_tasks.get(run_id)
    if task is None:
        return False
    task.cancel()
    return True


async def run_to_completion(run_id: str) -> None:
    """Awaits the same execution `start_run` schedules in the background,
    without the cancellation registry — for callers (the evaluation runner)
    that want to run one task at a time and wait for a real result rather
    than fire-and-forget via the API."""
    await _run_graph(run_id)
