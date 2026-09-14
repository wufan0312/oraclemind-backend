"""大六壬排盘路由：POST /api/v1/liuren/paipan。"""

from fastapi import APIRouter

from app.schemas.paipan import BasePaipanResponse, PaipanRequest, resolve_lunar_to_solar
from app.services.paipan.liuren import compute_liuren
from app.core.paipan_cache import cached_paipan

router = APIRouter(prefix="/liuren", tags=["排盘 · 大六壬"])


@router.post(
    "/paipan",
    response_model=BasePaipanResponse,
    summary="大六壬排盘",
    description="三式之一：按节气定月将、月将加占时布天地盘、起四课、按九宗门发三传、布十二天将。"
    "可选传 longitude（出生地经度）做真太阳时校正（生辰类排盘口径）。",
)
async def paipan(req: PaipanRequest) -> BasePaipanResponse:
    """大六壬起课：天地盘 + 四课 + 三传 + 天将。"""
    resolve_lunar_to_solar(req)
    result, _ = await cached_paipan(
        "liuren",
        req.model_dump(),
        lambda: compute_liuren(req.year, req.month, req.day, req.hour, req.gender,
                               req.timeText, req.question),
    )
    return BasePaipanResponse(**result)
