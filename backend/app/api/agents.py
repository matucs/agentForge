from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AgentOut
from app.db.repositories import AgentRepository
from app.db.session import get_session

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
async def list_agents(session: AsyncSession = Depends(get_session)) -> list[AgentOut]:
    agents = await AgentRepository(session).list()
    return [AgentOut.model_validate(a) for a in agents]
