"""连通性示例路由。"""

from fastapi import APIRouter

router = APIRouter(tags=["示例"])


@router.get("/ping", summary="连通性测试")
async def ping() -> dict[str, str]:
    """最简连通性验证，确认服务在线。"""
    return {"message": "pong"}
