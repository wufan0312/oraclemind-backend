"""报告服务 API —— 统一 Owner 模型：登录用户按账号隔离，匿名用户按访客ID隔离。

数据存储重设计方案 §三：
- 带 Bearer token → 写入/查询绑定 user_id（owner_type='user'）
- 未登录 → 写入/查询绑定 visitor_id（owner_type='visitor'）

报告管理增强（对应《报告页面功能缺失分析》）：
- #2 搜索：list_reports 支持 q 关键词 / dateFrom~dateTo 日期范围 / favorited
- #3 越权：详情、删除、收藏、批注全部走 _is_report_owner
- #5 收藏/置顶：PATCH /reports/{id}/favorite
- #7 批量删除：POST /reports/batch-delete
- #8 批注：/reports/{id}/annotations CRUD
- #12 版本：GET /reports/{id}/versions
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.api.v1.auth import get_optional_user, get_visitor_id
from app.core.audit import audited_commit
from app.core.config import settings
from app.core.ownership import actor_id_of, require_identity
from app.db.session import get_db
from app.models.report import Report
from app.models.report_annotation import ReportAnnotation
from app.models.user import User
from app.schemas.report import (
    AnnotationCreate,
    AnnotationOut,
    AnnotationUpdate,
    ReportBatchDelete,
    ReportCreate,
    ReportFavoriteUpdate,
    ReportListItem,
    ReportOut,
)

router = APIRouter(tags=["报告"])

# 搜索时最多在内存中过滤的候选条数：单身份报告量上限 100，
# 留 10 倍余量足够覆盖，同时挡住「全表拉进内存」的性能风险。
# 阈值收敛到 settings.search_scan_cap（Q5）。


def _is_report_owner(report: Report, user: User | None, visitor_id: str | None) -> bool:
    """归属权判定（防水平越权，对应缺陷报告 P0-2）。

    - 已登录：须为 user_id 所有者且 owner_type='user'
    - 匿名：须匹配 visitor_id 且 owner_type='visitor'
    - 无身份又无 visitorId：一律不可访问
    """
    if user is not None:
        return report.owner_type == "user" and report.user_id == user.id
    if visitor_id:
        return report.owner_type == "visitor" and report.visitor_id == visitor_id
    return False


def _owner_filter(user: User | None, visitor_id: str | None):
    """按身份构造归属过滤条件；无身份返回 None（调用方应直接返回空）。"""
    if user is not None:
        return (Report.user_id == user.id,)
    if visitor_id:
        return (Report.visitor_id == visitor_id,)
    return None


async def _get_owned_report(
    report_id: int, user: User | None, visitor_id: str | None, db: AsyncSession
) -> Report:
    """取报告并校验归属；不存在/无权一律 404（不暴露资源存在性）。"""
    report = await db.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")
    if not _is_report_owner(report, user, visitor_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")
    return report


# 术数模块 key（results 字典里的排盘模块名，用于分类推导）
_DIVINATION_KEYS = {"bazi", "ziwei", "liuyao", "meihua", "qimen", "liuren", "taiyi", "wuxing"}


def _classify_types(results) -> list[str]:
    """从 results 快照推导报告分类（前端筛选 tab 依赖的稳定值）。

    历史包袱：旧实现直接 ``list(results.keys())``，把模块原始 key（bazi/ziwei/…）
    当分类返回，导致列表 meta 行显示英文 key 串、且「综合报告/塔罗/卜卦」筛选全部
    落空归「其他」。这里统一归一为四类：report / tarot / bugua / other。
    派生计算、不落库 —— 存量数据无需迁移，改完即生效。
    """
    if not results:
        return []
    keys = set(results.keys())
    if "report" in keys:
        return ["report"]
    if "tarot" in keys:
        return ["tarot"]
    hits = keys & _DIVINATION_KEYS
    if len(hits) >= 2:
        return ["report"]  # 多术数综合命盘
    if hits:
        return ["bugua"]  # 单术数卜卦存档
    return ["other"]


def _to_list_item(r: Report) -> ReportListItem:
    return ReportListItem(
        id=r.id,
        visitorId=r.visitor_id,
        title=r.title,
        params=r.params,
        types=_classify_types(r.results),
        created_at=r.created_at,
        favorited=bool(r.favorited),
        pinned=bool(r.pinned),
        parentId=r.parent_id,
        variant=r.variant or 0,
    )


def _assemble_version_chain(root: Report, children: list[Report]) -> list[Report]:
    """从根出发，按 ``parent_id`` 在 children 池中挑出整条版本链子树（有界 BFS，纯函数）。

    用于 R4 修复：把"加载 owner 全部报告再 BFS"改为"只取链上节点"。``children`` 须为
    已按 owner 过滤、且排除软删的候选节点（通常已用 ``load_only`` 只取列表列）。
    """
    by_parent: dict[int, list[Report]] = {}
    for r in children:
        if r.parent_id is not None:
            by_parent.setdefault(r.parent_id, []).append(r)
    chain: list[Report] = [root]
    seen: set[int] = {root.id}
    frontier = [root.id]
    for _ in range(50):  # 上限防异常成环数据造成无限循环
        nxt: list[Report] = []
        for pid in frontier:
            for c in by_parent.get(pid, []):
                if c.id not in seen:
                    seen.add(c.id)
                    chain.append(c)
                    nxt.append(c)
        frontier = [c.id for c in nxt]
        if not frontier:
            break
    chain.sort(key=lambda r: (r.variant or 0, r.created_at))
    return chain



def _matches_keyword(r: Report, kw: str) -> bool:
    """关键词匹配：标题 + 提问 + 姓名 + 摘要。

    params 是 JSON，跨库（SQLite/PG）做 LIKE 语义不一致，且单身份报告量小，
    这里在内存中匹配 —— 语义统一、可控，且避免 JSON 方言分支。
    P1 修复（S8）：不再读取 ``results`` 大 JSON 列（候选扫描已 load_only 排除），
    仅基于标题/提问/姓名/摘要匹配，避免把整行大 JSON 拉进内存。
    """
    params = r.params if isinstance(r.params, dict) else {}
    haystack_parts = [
        r.title or "",
        str(params.get("question") or ""),
        str(params.get("name") or ""),
    ]
    summary = r.summary if isinstance(r.summary, dict) else {}
    if summary.get("summary"):
        haystack_parts.append(str(summary["summary"]))
    return kw in "\n".join(haystack_parts).lower()


@router.post(
    "/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="保存综合排盘报告（按身份隔离）",
)
async def create_report(
    payload: ReportCreate,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> Report:
    """保存一次排盘会话（输入参数 + 各术数结果快照）。

    - 已登录：归属账号（user_id + owner_type='user'）
    - 未登录：必须提供 visitorId，归属匿名（owner_type='visitor'）
    """
    if user is not None:
        report = Report(
            user_id=user.id,
            visitor_id=payload.visitorId or "",
            owner_type="user",
            title=payload.title,
            params=payload.params,
            results=payload.results,
            summary=payload.summary,
        )
    else:
        require_identity(user, payload.visitorId)
        report = Report(
            visitor_id=payload.visitorId,
            owner_type="visitor",
            title=payload.title,
            params=payload.params,
            results=payload.results,
            summary=payload.summary,
        )
    report.variant = max(0, int(payload.variant or 0))
    if payload.parentId is not None and payload.parentId > 0:
        parent = await db.get(Report, payload.parentId)
        # 版本链只能挂在属于自己的报告上，防越权串联他人报告
        if parent is not None and _is_report_owner(parent, user, payload.visitorId):
            report.parent_id = parent.id
            report.variant = max(report.variant, (parent.variant or 0) + 1)
    db.add(report)
    await db.flush()  # 先拿 report.id 供审计引用，仍在事务内（未提交）
    # 审计：排盘保存（合规 §4.6）—— 与 report 同一事务，一次 commit 一起落库（P1-5）
    await audited_commit(
        db,
        "create_report",
        actor_type=report.owner_type,
        actor_id=actor_id_of(user, payload.visitorId),
        target=str(report.id),
    )
    await db.refresh(report)
    return report


@router.get("/reports", response_model=list[ReportListItem], summary="报告列表（按身份隔离，支持关键词/日期/收藏筛选）")
async def list_reports(
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    limit: int = Query(20, ge=1, le=100),
    # 缺陷报告 P2-11：offset 仅 ge=0 校验，恶意 offset=99999999 会触发大范围扫描。
    # 设上限 100000，既覆盖正常用户（数据按身份隔离，单用户报告量有限），又挡住越界扫描。
    offset: int = Query(0, ge=0, le=100000),
    # --- #2 搜索能力：关键词 / 日期范围 / 仅看收藏 ---
    q: str | None = Query(None, max_length=64, description="关键词（标题/提问/术数/摘要）"),
    dateFrom: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    dateTo: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    favorited: bool | None = Query(None, description="仅看收藏（true）"),
    db: AsyncSession = Depends(get_db),
) -> list[ReportListItem]:
    """分页返回当前身份的报告列表；types 字段由 results 的 key 推导，不含完整结果。

    置顶 > 收藏 > 时间倒序：重要报告不会被新报告淹没（#5）。
    """
    conds = _owner_filter(user, visitorId)
    if conds is None:
        return []
    stmt = select(Report).where(Report.deleted_at.is_(None), *conds)

    # 收藏筛选走 SQL（无需读 results，代价最低）；关键词与日期需要在内存里过滤
    if favorited is True:
        stmt = stmt.where(Report.favorited.is_(True))

    # 有关键词/日期筛选时，先在候选集内过滤（候选量按身份隔离且有上限）
    kw = (q or "").strip().lower()
    start = _parse_date(dateFrom)
    end = _parse_date(dateTo)
    need_memory_filter = bool(kw) or start is not None or end is not None
    if not need_memory_filter:
        stmt = stmt.order_by(Report.pinned.desc(), Report.favorited.desc(), Report.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        rows = (await db.execute(stmt)).scalars().all()
        return [_to_list_item(r) for r in rows]

    # --- 关键词/日期路径：取候选集 → 内存匹配 → 分页 ---
    # P1 修复（S8）：候选扫描用 load_only 排除 results 大 JSON 列，仅取列表/匹配所需字段，
    # 避免把最多 settings.search_scan_cap 行（默认 1000）完整 results JSON 拉进内存导致 OOM。
    candidates = (
        await db.execute(
            select(Report)
            .options(
                load_only(
                    Report.id,
                    Report.visitor_id,
                    Report.title,
                    Report.params,
                    Report.summary,
                    Report.created_at,
                    Report.favorited,
                    Report.pinned,
                    Report.parent_id,
                    Report.variant,
                )
            )
            .where(Report.deleted_at.is_(None), *conds)
            .order_by(Report.created_at.desc())
            .limit(settings.search_scan_cap)
        )
    ).scalars().all()

    matched = [r for r in candidates if (not kw or _matches_keyword(r, kw))]
    if favorited is True:
        matched = [r for r in matched if r.favorited]
    matched = _filter_by_range(matched, start, end)
    # 置顶 > 收藏 > 时间倒序
    matched.sort(
        key=lambda r: (not r.pinned, not r.favorited, -(r.created_at.timestamp() if r.created_at else 0))
    )
    page = matched[offset : offset + limit]
    if not page:
        return []
    # 仅最终页切片（≤ limit）回查完整行以取 results 类型清单，避免大 JSON 批量入内存
    full_rows = (
        await db.execute(select(Report).where(Report.id.in_([r.id for r in page])))
    ).scalars().all()
    full_map = {r.id: r for r in full_rows}
    return [_to_list_item(full_map[r.id]) for r in page]


def _filter_by_range(
    rows: list[Report], start: datetime | None, end: datetime | None
) -> list[Report]:
    """按日期范围过滤；end 含当天（补到 23:59:59）。两端都为 None 时原样返回。"""
    if start is None and end is None:
        return rows
    # 含当天：end 推进到当日最后一微秒
    end_inclusive = end + timedelta(days=1) - timedelta(microseconds=1) if end else None
    out: list[Report] = []
    for r in rows:
        ts = r.created_at
        if ts is None:
            continue
        # SQLite 取出的是 naive datetime（存的是 UTC），统一按 UTC 比较
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if start is not None and ts < start:
            continue
        if end_inclusive is not None and ts > end_inclusive:
            continue
        out.append(r)
    return out


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.strptime(s.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return d.replace(tzinfo=timezone.utc)


@router.get("/reports/count", response_model=dict, summary="报告总数（按身份隔离）")
async def count_reports(
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conds = _owner_filter(user, visitorId)
    if conds is None:
        return {"total": 0}
    stmt = select(func.count(Report.id)).where(Report.deleted_at.is_(None), *conds)
    total = await db.scalar(stmt)
    return {"total": total or 0}


@router.get("/reports/{report_id}", response_model=ReportOut, summary="报告详情")
async def get_report(
    report_id: int,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> Report:
    return await _get_owned_report(report_id, user, visitorId, db)


@router.patch("/reports/{report_id}/favorite", response_model=ReportListItem, summary="收藏/置顶报告")
async def update_favorite(
    report_id: int,
    payload: ReportFavoriteUpdate,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> ReportListItem:
    """更新收藏/置顶状态（#5）。仅所有者可改，参数缺省则保持原值。"""
    if payload.favorited is None and payload.pinned is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="favorited / pinned 至少提供一个")
    report = await _get_owned_report(report_id, user, visitorId, db)
    if payload.favorited is not None:
        report.favorited = bool(payload.favorited)
    if payload.pinned is not None:
        report.pinned = bool(payload.pinned)
    await audited_commit(
        db,
        "favorite_report",
        actor_type=report.owner_type,
        actor_id=actor_id_of(user, visitorId),
        target=str(report.id),
    )
    await db.refresh(report)
    return _to_list_item(report)


@router.post("/reports/batch-delete", response_model=dict, summary="批量删除报告（软删，最多 100 条）")
async def batch_delete_reports(
    payload: ReportBatchDelete,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """批量软删（#7）：逐条走归属校验，越权 ID 直接跳过且不计入成功数。"""
    now = datetime.now(timezone.utc)
    deleted = 0
    skipped = 0
    for rid in payload.ids:
        report = await db.get(Report, rid)
        if report is None or report.deleted_at is not None:
            skipped += 1
            continue
        if not _is_report_owner(report, user, visitorId):
            skipped += 1
            continue
        report.deleted_at = now
        deleted += 1
    if deleted:
        await audited_commit(
            db,
            "batch_delete_reports",
            actor_type="user" if user is not None else "visitor",
            actor_id=actor_id_of(user, visitorId),
            target=f"count={deleted},skipped={skipped}",
        )
    return {"deleted": deleted, "skipped": skipped}


@router.get("/reports/{report_id}/versions", response_model=list[ReportListItem], summary="报告版本链（换个说法的历史版本）")
async def list_report_versions(
    report_id: int,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> list[ReportListItem]:
    """返回同一版本链上的全部版本（#12）：先回溯到根，再列出根的所有子孙。

    R4 修复：原实现用 ``select(Report).where(conds)`` 把该 owner 的**全部**报告
    （含大体积 ``results`` JSON）一次性拉进内存再 BFS 组装，单身份报告量大时易 OOM。
    改为沿 ``parent_id`` 做有界查询，只取版本链节点（根 + 其子孙），且只加载列表所需列。
    """
    current = await _get_owned_report(report_id, user, visitorId, db)
    root = current
    # 回溯到根（链深有限，加 50 次上限防异常数据成环）
    for _ in range(50):
        if not root.parent_id:
            break
        parent = await db.get(Report, root.parent_id)
        if parent is None:
            break
        root = parent
    conds = _owner_filter(user, visitorId)
    if conds is None:
        return []

    # 仅取列表展示所需列（含 results 供 types 字段），避免整行/全量拉取
    _list_cols = (
        Report.id, Report.visitor_id, Report.title, Report.params,
        Report.results, Report.created_at, Report.favorited,
        Report.pinned, Report.parent_id, Report.variant,
    )
    # 有界 BFS：按 parent_id 逐层取根的所有子孙（depth/节点上限 50），只加载链上节点
    children: list[Report] = []
    visited: set[int] = {root.id}
    frontier = [root.id]
    for _ in range(50):
        rows = (
            await db.execute(
                select(Report)
                .options(load_only(*_list_cols))
                .where(Report.deleted_at.is_(None), *conds, Report.parent_id.in_(frontier))
                .order_by(Report.created_at.asc())
            )
        ).scalars().all()
        if not rows:
            break
        nxt: list[int] = []
        for r in rows:
            if r.id in visited:
                continue
            visited.add(r.id)
            children.append(r)
            nxt.append(r.id)
        frontier = nxt
        if not frontier:
            break

    chain = _assemble_version_chain(root, children)
    return [_to_list_item(r) for r in chain]


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除报告（软删）")
async def delete_report(
    report_id: int,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    report = await _get_owned_report(report_id, user, visitorId, db)
    # 软删：仅标记 deleted_at，物理删除需 GDPR 显式请求（合规 §4.6）
    report.deleted_at = datetime.now(timezone.utc)
    # 审计与软删同事务，一次 commit 一起生效（P1-5）
    await audited_commit(
        db,
        "delete_report",
        actor_type=report.owner_type,
        actor_id=actor_id_of(user, visitorId),
        target=str(report.id),
    )


# ============================= 报告批注（#8） =============================


@router.get("/reports/{report_id}/annotations", response_model=list[AnnotationOut], summary="报告批注列表")
async def list_annotations(
    report_id: int,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> list[AnnotationOut]:
    """列出当前身份在该报告上的批注（报告本身也要归属校验，防越权读他人批注）。"""
    await _get_owned_report(report_id, user, visitorId, db)
    stmt = select(ReportAnnotation).where(ReportAnnotation.report_id == report_id)
    if user is not None:
        stmt = stmt.where(ReportAnnotation.user_id == user.id)
    elif visitorId:
        stmt = stmt.where(ReportAnnotation.visitor_id == visitorId)
    else:
        return []
    stmt = stmt.order_by(ReportAnnotation.created_at.asc())
    rows = (await db.execute(stmt)).scalars().all()
    return [AnnotationOut.model_validate(r) for r in rows]


@router.post("/reports/annotations", response_model=AnnotationOut, status_code=status.HTTP_201_CREATED, summary="新增批注")
async def create_annotation(
    payload: AnnotationCreate,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> AnnotationOut:
    await _get_owned_report(payload.reportId, user, payload.visitorId, db)
    ann = ReportAnnotation(
        report_id=payload.reportId,
        user_id=user.id if user is not None else None,
        visitor_id=payload.visitorId or "",
        owner_type="user" if user is not None else "visitor",
        anchor=payload.anchor,
        anchor_label=payload.anchorLabel,
        quote=payload.quote,
        content=payload.content,
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return AnnotationOut.model_validate(ann)


@router.patch("/reports/annotations/{annotation_id}", response_model=AnnotationOut, summary="修改批注")
async def update_annotation(
    annotation_id: int,
    payload: AnnotationUpdate,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> AnnotationOut:
    ann = await db.get(ReportAnnotation, annotation_id)
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批注不存在")
    # 批注归属校验：登录按 user_id，匿名按 visitor_id
    if user is not None:
        if ann.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批注不存在")
    elif visitorId:
        if ann.visitor_id != visitorId:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批注不存在")
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批注不存在")
    ann.content = payload.content
    await db.commit()
    await db.refresh(ann)
    return AnnotationOut.model_validate(ann)


@router.delete("/reports/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除批注")
async def delete_annotation(
    annotation_id: int,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    ann = await db.get(ReportAnnotation, annotation_id)
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批注不存在")
    if user is not None:
        if ann.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批注不存在")
    elif visitorId:
        if ann.visitor_id != visitorId:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批注不存在")
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批注不存在")
    await db.delete(ann)
    await db.commit()
