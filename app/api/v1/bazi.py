"""八字排盘路由：POST /api/v1/bazi/paipan。"""

from fastapi import APIRouter

from app.schemas.paipan import (
    BasePaipanResponse,
    PaipanRequest,
    apply_true_solar,
    resolve_lunar_to_solar,
)
from app.services.paipan.bazi import compute_bazi
from app.core.paipan_cache import cached_paipan

router = APIRouter(prefix="/bazi", tags=["排盘 · 八字"])


@router.post(
    "/paipan",
    response_model=BasePaipanResponse,
    summary="八字排盘",
    description="输入公历出生年/月/日/时，基于 lunar-python（寿星天文历）返回四柱、十神、五行能量、大运、流年、格局与用神喜忌。"
    "可选传 longitude（出生地经度）由后端做真太阳时校正后再定盘，结果附 trueSolarTime 详情。",
)
async def paipan(req: PaipanRequest) -> BasePaipanResponse:
    """八字排盘：日主/四柱/十神/大运/用神。"""
    resolve_lunar_to_solar(req)
    # 真太阳时校正：生辰类排盘必须先校正再定盘，否则东/西部出生者时柱可能整体偏移
    tst = apply_true_solar(req)
    result, _ = await cached_paipan(
        "bazi",
        req.model_dump(),
        lambda: compute_bazi(req.year, req.month, req.day, req.hour, req.gender, req.timeText),
    )
    if tst:
        result["trueSolarTime"] = tst
    return BasePaipanResponse(**result)
