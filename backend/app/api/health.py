import redis.asyncio as redis
from fastapi import APIRouter

from app.config import get_settings
from app.db.session import check_database_connection

router = APIRouter(tags=["health"])


async def _check_redis() -> bool:
    settings = get_settings()
    try:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=1)
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        try:
            await client.aclose()
        except Exception:
            pass


@router.get("/api/health")
async def health() -> dict:
    settings = get_settings()
    db_ok = await check_database_connection()
    redis_ok = await _check_redis()

    return {
        "status": "healthy" if db_ok and redis_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "redis": "connected" if redis_ok else "unavailable",
        "llm_provider": {
            "default": settings.default_llm_provider,
            "anthropic_configured": bool(settings.anthropic_api_key),
            "openai_configured": bool(settings.openai_api_key),
        },
    }
