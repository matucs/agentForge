import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_reports_real_status() -> None:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"healthy", "degraded"}
    assert body["database"] in {"connected", "unavailable"}
    assert body["redis"] in {"connected", "unavailable"}
    assert "llm_provider" in body
