"""健康检查响应模型。"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """/api/health 返回体。"""

    status: str  # ok / degraded
    app: str
    version: str
    database: str  # up / down
    redis: str  # up / down
