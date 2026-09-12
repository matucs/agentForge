from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import WebhookTaskIn, WebhookTaskOut
from app.db.repositories import ProjectRepository, RunRepository, TaskRepository
from app.db.session import get_session
from app.orchestration.service import start_run

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/n8n", response_model=WebhookTaskOut, status_code=202)
async def n8n_webhook(
    payload: WebhookTaskIn, session: AsyncSession = Depends(get_session)
) -> WebhookTaskOut:
    """Spec §22: an external automation (n8n, a support-ticket flow per
    spec §19) posts a real task here. It goes through the exact same
    project/task/run creation and `start_run` path the dashboard's "new
    task" form uses — no separate simulated path for webhook-originated
    work."""
    if payload.project_id:
        project = await ProjectRepository(session).get(payload.project_id)
        if project is None:
            raise HTTPException(
                status_code=404, detail=f"Project {payload.project_id} not found"
            )
    elif payload.project_name and payload.repo_path:
        project = await ProjectRepository(session).get_by_name(payload.project_name)
        if project is None:
            project = await ProjectRepository(session).create(
                name=payload.project_name, repo_path=payload.repo_path, description=None
            )
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either project_id, or both project_name and repo_path.",
        )

    task = await TaskRepository(session).create(
        project_id=project.id, title=payload.title, requirement_text=payload.requirement_text
    )
    run = await RunRepository(session).create(task_id=task.id)
    await session.commit()

    await start_run(run.id)

    refreshed = await RunRepository(session).get(run.id)
    assert refreshed is not None
    return WebhookTaskOut(
        project_id=project.id, task_id=task.id, run_id=run.id, status=refreshed.status
    )
