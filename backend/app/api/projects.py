from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ProjectCreate, ProjectOut
from app.db.repositories import ProjectRepository
from app.db.session import get_session

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    payload: ProjectCreate, session: AsyncSession = Depends(get_session)
) -> ProjectOut:
    project = await ProjectRepository(session).create(
        name=payload.name, repo_path=payload.repo_path, description=payload.description
    )
    return ProjectOut.model_validate(project)


@router.get("", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectOut]:
    projects = await ProjectRepository(session).list()
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str, session: AsyncSession = Depends(get_session)
) -> ProjectOut:
    project = await ProjectRepository(session).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return ProjectOut.model_validate(project)
