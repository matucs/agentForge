from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.approvals import router as approvals_router
from app.api.evaluations import router as evaluations_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.operations import router as operations_router
from app.api.projects import router as projects_router
from app.api.runs import router as runs_router
from app.api.tasks import router as tasks_router
from app.api.webhooks import router as webhooks_router
from app.config import get_settings
from app.observability.logging import configure_logging
from app.observability.tracing import configure_tracing
from app.orchestration.graph import setup_checkpointer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    configure_tracing()
    await setup_checkpointer()
    yield


app = FastAPI(
    title="AgentForge API",
    description="Governed autonomous software engineering platform.",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = ["http://localhost:3000"]
_extra_origins = get_settings().extra_cors_origins
if _extra_origins:
    _cors_origins.extend(o.strip() for o in _extra_origins.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(runs_router)
app.include_router(agents_router)
app.include_router(approvals_router)
app.include_router(metrics_router)
app.include_router(evaluations_router)
app.include_router(operations_router)
app.include_router(webhooks_router)
