from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import OperationsSummary
from app.db.session import get_session
from app.observability.metrics import compute_operations_summary

router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("/summary", response_model=OperationsSummary)
async def operations_summary(
    session: AsyncSession = Depends(get_session),
) -> OperationsSummary:
    data = await compute_operations_summary(session)
    return OperationsSummary(**data)
