"""Per-node instrumentation: one real ToolCall row, one structured log line,
and one OpenTelemetry span per orchestration node execution — success or
failure, duration always recorded. This is the real data source behind
"agent_duration"/"agent_errors" in GET /api/metrics (spec §16), not an
estimate.
"""

import functools
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from opentelemetry.trace import Status, StatusCode

from app.db.repositories import ToolCallRepository
from app.db.session import async_session_factory
from app.observability.logging import get_logger
from app.observability.tracing import get_tracer
from app.orchestration.state import AgentState

_logger = get_logger(__name__)
_tracer = get_tracer(__name__)

# Bound to (and returning) the same TypeVar `F` — not a fixed Callable alias
# — so a decorated node keeps its exact original callable type as far as
# mypy/LangGraph's `add_node` overload resolution is concerned. A decorator
# typed as `Callable[[NodeFn], NodeFn]` type-checks identically at the
# decorator's own definition but erases that "this is genuinely an async
# def" specialness for the *caller's* overload resolution, which is exactly
# what broke `build_graph`'s `add_node(...)` calls until this was fixed.
F = TypeVar("F", bound=Callable[[AgentState], Awaitable[dict]])


def instrument_node(agent_name: str) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(state: AgentState) -> dict:
            run_id = state["run_id"]
            task_id = state["task_id"]
            started = time.monotonic()
            succeeded = True
            error_text: str | None = None

            with _tracer.start_as_current_span(agent_name) as span:
                span.set_attribute("run_id", run_id)
                span.set_attribute("task_id", task_id)
                try:
                    result = await fn(state)
                    return result
                except Exception as exc:
                    succeeded = False
                    error_text = str(exc)
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, error_text))
                    raise
                finally:
                    duration = time.monotonic() - started
                    span.set_attribute("duration_seconds", duration)
                    span.set_attribute("succeeded", succeeded)

                    _logger.info(
                        f"{agent_name}_node",
                        run_id=run_id,
                        task_id=task_id,
                        agent=agent_name,
                        duration=round(duration, 4),
                        status="succeeded" if succeeded else "failed",
                    )

                    async with async_session_factory() as session:
                        await ToolCallRepository(session).create(
                            run_id=run_id,
                            agent=agent_name,
                            tool_name=f"{agent_name}_node",
                            duration_seconds=duration,
                            succeeded=succeeded,
                            result_summary=error_text,
                        )
                        await session.commit()

        return wrapper  # type: ignore[return-value]

    return decorator
