from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.observability.metrics import render_metrics

router = APIRouter(tags=["metrics"])


@router.get("/api/metrics")
async def metrics(session: AsyncSession = Depends(get_session)) -> Response:
    body = await render_metrics(session)
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)
