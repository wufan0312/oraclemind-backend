"""天使数字路由：POST /api/v1/angel/parse、/sequence、/personal。

口径与前端 ``src/data/angelNumbers.ts`` 严格对齐（服务端为权威实现，
前端保留本地表作为后端不可用时的降级兜底）。
"""

from fastapi import APIRouter, HTTPException

from app.schemas.angel import (
    AngelParseRequest,
    AngelParseResponse,
    AngelPersonalRequest,
    AngelPersonalResponse,
    AngelSequenceRequest,
    AngelSequenceResponse,
)
from app.services.paipan.angel_number import (
    analyze_sequence,
    compute_angel_number,
    parse_angel_number,
)

router = APIRouter(prefix="/angel", tags=["排盘 · 天使数字"])


@router.post(
    "/parse",
    response_model=AngelParseResponse,
    summary="天使数字解析（单个数）",
    description="归一化输入（支持 '1111' / '11:11' / '1 2 3' / 带空格或分隔符），返回命中的释义条目、是否重复型、逐位拆解。",
)
async def parse(req: AngelParseRequest) -> AngelParseResponse:
    """单个数解析：无数字 / 超长输入返回 400，绝不 500。"""
    try:
        result = parse_angel_number(req.raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AngelParseResponse(**result)


@router.post(
    "/sequence",
    response_model=AngelSequenceResponse,
    summary="天使数字序列分析",
    description="输入近期反复看到的多个数字，统计出现频次、归纳主题关键词，回答「我最近到底在被提醒什么」。",
)
async def sequence(req: AngelSequenceRequest) -> AngelSequenceResponse:
    """序列分析：空列表 / 全部无法解析返回 400。"""
    try:
        result = analyze_sequence(req.numbers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AngelSequenceResponse(**result)


@router.post(
    "/personal",
    response_model=AngelPersonalResponse,
    summary="个人天使数字（民俗算法）",
    description="由出生日期按生命数法（数字根）推导个人天使数字。属民俗算法，非典籍命理结论。",
)
async def personal(req: AngelPersonalRequest) -> AngelPersonalResponse:
    """个人天使数字：日期格式非法返回 400。"""
    try:
        result = compute_angel_number(req.birthDate, req.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AngelPersonalResponse(**result)
