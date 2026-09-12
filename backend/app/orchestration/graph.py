from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.orchestration.nodes import (
    architect_node,
    developer_node,
    planner_node,
    policy_node,
    qa_node,
    researcher_node,
    reviewer_node,
    security_node,
    verification_node,
)
from app.orchestration.routing import route_after_qa, route_after_reviewer
from app.orchestration.state import AgentState


def _checkpointer_conn_string() -> str:
    """AsyncPostgresSaver uses psycopg, not asyncpg — the domain schema's
    driver (see ADR-002). Same database, a separate driver/connection pool
    dedicated to checkpoint storage, per the LangGraph-recommended setup.

    A managed Postgres provider that requires TLS (e.g. Neon) needs
    `?ssl=require` in DATABASE_URL for asyncpg/SQLAlchemy — but psycopg/libpq
    has no `ssl` query parameter, only `sslmode`, and rejects an unknown one
    outright. Translate it rather than assume DATABASE_URL never carries a
    query string, which the previous plain scheme-replace did."""
    settings = get_settings()
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parts = urlsplit(url)
    query_pairs = [
        ("sslmode", value) if key == "ssl" else (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((*parts[:3], urlencode(query_pairs), parts.fragment))


@asynccontextmanager
async def checkpointer_context() -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(_checkpointer_conn_string()) as saver:
        yield saver


async def setup_checkpointer() -> None:
    """Creates the checkpointer's own tables. Called once at backend
    startup (see app/main.py) — idempotent."""
    async with checkpointer_context() as saver:
        await saver.setup()


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("architect", architect_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("developer", developer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("qa", qa_node)
    graph.add_node("security", security_node)
    graph.add_node("verification", verification_node)
    graph.add_node("policy", policy_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "architect")
    graph.add_edge("architect", "researcher")
    graph.add_edge("researcher", "developer")
    graph.add_edge("developer", "reviewer")
    graph.add_conditional_edges(
        "reviewer", route_after_reviewer, {"developer": "developer", "qa": "qa"}
    )
    graph.add_conditional_edges(
        "qa", route_after_qa, {"developer": "developer", "security": "security"}
    )
    graph.add_edge("security", "verification")
    graph.add_edge("verification", "policy")
    graph.add_edge("policy", END)

    return graph
