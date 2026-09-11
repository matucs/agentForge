from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.runs import router as runs_router
from app.api.tasks import router as tasks_router

app = FastAPI(
    title="AgentForge API",
    description="Governed autonomous software engineering platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(runs_router)
app.include_router(agents_router)
