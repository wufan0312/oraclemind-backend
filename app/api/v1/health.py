"""健康检查 —— 服务本身 + PostgreSQL + Redis 状态。"""

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import check_database, check_redis
from app.schemas.health import HealthResponse

router = APIRouter(tags=["系统"])


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health() -> HealthResponse:
    """返回应用与依赖（PostgreSQL / Redis）的连接状态。

    - 全部就绪：`status=ok`，HTTP 200
    - 任一依赖降级：`status=degraded`，HTTP 503（服务本身仍可响应）
    """
    db_up = await check_database()
    redis_up = await check_redis()

    return HealthResponse(
        status="ok" if (db_up and redis_up) else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        database="up" if db_up else "down",
        redis="up" if redis_up else "down",
    )
