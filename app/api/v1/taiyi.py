"""太乙神数排局路由：POST /api/v1/taiyi/paipan。"""

from fastapi import APIRouter

from app.schemas.paipan import BasePaipanResponse, PaipanRequest, resolve_lunar_to_solar
from app.services.paipan.taiyi import compute_taiyi
from app.core.paipan_cache import cached_paipan

router = APIRouter(prefix="/taiyi", tags=["排盘 · 太乙神数"])


@router.post(
    "/paipan",
    response_model=BasePaipanResponse,
    summary="太乙神数排局",
    description="三式之一：太乙积年 → 行宫（三年一徙、不入中五）→ 阴阳遁 → 文昌/始击/计神/合神 "
    "→ 主客算 → 主客大将参将 → 十六宫神位。流派分歧大，结果附 provenance 说明所采之说。",
)
async def paipan(req: PaipanRequest) -> BasePaipanResponse:
    """太乙神数年计排局。"""
    resolve_lunar_to_solar(req)
    result, _ = await cached_paipan(
        "taiyi",
        req.model_dump(),
        lambda: compute_taiyi(req.year, req.month, req.day, req.hour, req.gender,
                              req.timeText, req.question),
    )
    return BasePaipanResponse(**result)
