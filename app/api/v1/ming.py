"""测字 / 姓名五格 / 合婚 路由（P2-2）：POST /api/v1/ming/{wuge,hehun,cezi}。

此前这套算法只在前端 `src/lib/ceming.ts`，无服务端权威、无测试。
这里把确定性部分下沉后端，**汉字笔画由调用方传入**（笔画属字典能力，前端 cnchar 更全）。
"""

from fastapi import APIRouter, HTTPException

from app.schemas.ceming import (
    CeziRequest,
    CeziResponse,
    HehunBaziRequest,
    HehunRequest,
    HehunResponse,
    WugeRequest,
    WugeResponse,
)
from app.services.paipan.ceming import compute_cezi, compute_hehun, compute_wuge

router = APIRouter(prefix="/ming", tags=["排盘 · 测字姓名"])


@router.post(
    "/wuge",
    response_model=WugeResponse,
    summary="姓名五格剖象",
    description="传入姓/名及其各字笔画，返回天格/人格/地格/外格/总格的 81 数理与吉凶、三才配置、综合评分。",
)
async def wuge(req: WugeRequest) -> WugeResponse:
    try:
        res = compute_wuge(req.surnameStrokes, req.givenStrokes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return WugeResponse(surname=req.surname, given=req.given, **res)


@router.post(
    "/hehun",
    response_model=HehunResponse,
    summary="合婚（生肖 + 五行互补）",
    description="传入双方年支（生肖地支），返回六合/六冲/六害/三合/三刑、天干五合与五行互补评分。",
)
async def hehun(req: HehunRequest) -> HehunResponse:
    try:
        res = compute_hehun(
            req.maleZhi,
            req.femaleZhi,
            male_gan=req.maleGan,
            female_gan=req.femaleGan,
            male_wuxing=req.maleWuxing,
            female_wuxing=req.femaleWuxing,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return HehunResponse(**res)


@router.post(
    "/cezi",
    response_model=CeziResponse,
    summary="测字取象",
    description="按码点取五行、配八卦、断走势（与前端 analyzeCezi 同口径）。",
)
async def cezi(req: CeziRequest) -> CeziResponse:
    try:
        res = compute_cezi(req.char, req.strokes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CeziResponse(**res)


@router.post(
    "/hehun-bazi",
    response_model=HehunResponse,
    summary="八字合婚（日干 + 五行互补）",
    description="传入双方八字推导出的日干与五行计数，复用 compute_hehun 做天干五合与五行互补评分；可附年支做生肖关系。",
)
async def hehun_bazi(req: HehunBaziRequest) -> HehunResponse:
    try:
        res = compute_hehun(
            req.maleZhi or "",
            req.femaleZhi or "",
            male_gan=req.maleDayGan or None,
            female_gan=req.femaleDayGan or None,
            male_wuxing=req.maleWuxing or None,
            female_wuxing=req.femaleWuxing or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return HehunResponse(**res)
