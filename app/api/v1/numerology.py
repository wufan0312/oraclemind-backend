"""数字命理排盘路由：POST /api/v1/numerology/paipan。"""

from fastapi import APIRouter

from app.schemas.numerology import NumerologyRequest, NumerologyResponse
from app.services.paipan.numerology import compute_num
from app.core.paipan_cache import cached_paipan

router = APIRouter(prefix="/numerology", tags=["排盘 · 数字命理"])


@router.post(
    "/paipan",
    response_model=NumerologyResponse,
    summary="数字命理排盘",
    description="输入农历出生年/月/日（可选中文姓名），返回生命灵数、生日数、九宫格统计、缺数、未来 9 年流年与核心数字（与前端原型算法一致）。",
)
async def paipan(req: NumerologyRequest) -> NumerologyResponse:
    """数字命理排盘：算法与前端 computeNum 完全对齐。"""
    result, _ = await cached_paipan(
        "numerology",
        req.model_dump(),
        lambda: compute_num(req.year, req.month, req.day, name=req.name),
    )
    return NumerologyResponse(**result)
