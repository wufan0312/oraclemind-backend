"""六爻 / 梅花易数排盘路由：POST /api/v1/gua/liuyao、/api/v1/gua/meihua。"""

from fastapi import APIRouter

from app.schemas.paipan import BasePaipanResponse, PaipanRequest, resolve_lunar_to_solar
from app.services.paipan.liuyao import compute_liuyao
from app.services.paipan.meihua import compute_meihua
from app.core.paipan_cache import cached_paipan

router = APIRouter(prefix="/gua", tags=["排盘 · 六爻 / 梅花易数"])


@router.post(
    "/liuyao",
    response_model=BasePaipanResponse,
    summary="六爻起卦",
    description="时间起卦：本卦/变卦、纳甲六亲、世应、动爻，并按问题关键词取用神。",
)
async def liuyao(req: PaipanRequest) -> BasePaipanResponse:
    """六爻起卦排盘。"""
    resolve_lunar_to_solar(req)
    result, _ = await cached_paipan(
        "liuyao",
        req.model_dump(),
        lambda: compute_liuyao(req.year, req.month, req.day, req.hour, req.gender, req.timeText, req.question, req.method, req.linesInput),
    )
    return BasePaipanResponse(**result)


@router.post(
    "/meihua",
    response_model=BasePaipanResponse,
    summary="梅花易数起卦",
    description="梅花易数起卦：支持 time 时间 / number 数字 / text 字数 / manual 手动指定；"
                "含本互变三卦、体用生克、体用旺衰、卦辞爻辞。",
)
async def meihua(req: PaipanRequest) -> BasePaipanResponse:
    """梅花易数起卦排盘。"""
    resolve_lunar_to_solar(req)
    result, _ = await cached_paipan(
        "meihua",
        req.model_dump(),
        lambda: compute_meihua(
            req.year, req.month, req.day, req.hour, req.gender, req.timeText, req.question,
            req.method, req.num1, req.num2, req.shangNum, req.xiaNum, req.dongNum,
            req.numType or "xian",
        ),
    )
    return BasePaipanResponse(**result)
