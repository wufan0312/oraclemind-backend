"""紫微斗数排盘路由：POST /api/v1/ziwei/paipan。"""

from fastapi import APIRouter

from app.schemas.paipan import (
    BasePaipanResponse,
    PaipanRequest,
    ZiweiTimelineRequest,
    apply_true_solar,
    resolve_lunar_to_solar,
)
from app.services.paipan.ziwei import compute_ziwei
from app.core.paipan_cache import cached_paipan

router = APIRouter(prefix="/ziwei", tags=["排盘 · 紫微斗数"])


@router.post(
    "/paipan",
    response_model=BasePaipanResponse,
    summary="紫微斗数排盘",
    description="输入公历出生年/月/日/时，按传统安星法返回命身宫、五行局、十四主星/辅星十二宫、四化与命格特质。"
    "可选传 longitude（出生地经度）由后端做真太阳时校正后再安星（命宫由生月+生时推定，时辰偏差会整盘错位）。",
)
async def paipan(req: PaipanRequest) -> BasePaipanResponse:
    """紫微斗数排盘：安星法（自研）。"""
    resolve_lunar_to_solar(req)
    # 真太阳时校正：命宫/身宫由生时推定，时辰错则整盘错，故与八字同样先校正
    tst = apply_true_solar(req)
    result, _ = await cached_paipan(
        "ziwei",
        req.model_dump(),
        lambda: compute_ziwei(req.year, req.month, req.day, req.hour, req.gender, req.timeText),
    )
    if tst:
        result["trueSolarTime"] = tst
    return BasePaipanResponse(**result)


@router.post(
    "/timeline",
    summary="紫微斗数 流年/流月 指定年份查询",
    description="给定出生信息与目标年份，返回该年流年命盘；若带 targetMonth 则返回该年 12 流月列表，用于年份/月份切换浏览。",
)
async def timeline(req: ZiweiTimelineRequest) -> dict:
    """流年/流月 指定年份查询（P0：可切换年份/月份）。"""
    resolve_lunar_to_solar(req)
    # 与 /paipan 保持一致：流年盘也建立在校正后的生辰上
    apply_true_solar(req)
    result, _ = await cached_paipan(
        "ziwei-timeline",
        req.model_dump(),
        lambda: compute_ziwei(
            req.year, req.month, req.day, req.hour, req.gender, req.timeText,
            target_year=req.targetYear, target_month=req.targetMonth,
        ),
    )
    return {
        "liuNian": result["liuNian"],
        "liuYueList": result["liuYueByYear"].get(req.targetYear, []),
        "liuNianSihua": result.get("liuNianSihua"),
    }
