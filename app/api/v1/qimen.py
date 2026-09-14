"""奇门遁甲排盘路由：POST /api/v1/qimen/paipan。"""

from fastapi import APIRouter

from app.schemas.paipan import BasePaipanResponse, PaipanRequest, resolve_lunar_to_solar
from app.services.paipan.qimen import compute_qimen
from app.core.paipan_cache import cached_paipan

router = APIRouter(prefix="/qimen", tags=["排盘 · 奇门遁甲"])


@router.post(
    "/paipan",
    response_model=BasePaipanResponse,
    summary="奇门遁甲排盘",
    description="时家奇门·拆补法：定阴阳遁局数，排九宫（九星/八门/八神/三奇六仪），输出三奇方位与行动指南。",
)
async def paipan(req: PaipanRequest) -> BasePaipanResponse:
    """奇门遁甲排盘：拆补法定局 + 九宫排盘。"""
    resolve_lunar_to_solar(req)
    manual_ju = None
    if req.qimen_ju:
        manual_ju = (req.qimen_ju.get("yinyang"), req.qimen_ju.get("ju"))
    result, _ = await cached_paipan(
        "qimen",
        req.model_dump(),
        lambda: compute_qimen(req.year, req.month, req.day, req.hour, req.gender, req.timeText, req.question,
                              manual_ju=manual_ju),
    )
    return BasePaipanResponse(**result)
