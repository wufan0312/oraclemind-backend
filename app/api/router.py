"""API 总路由 —— 统一挂载各版本路由。"""

from fastapi import APIRouter

from app.api.v1 import (
    angel,
    auth,
    bazi,
    community,
    donations,
    gua,
    health,
    ming,
    numerology,
    ping,
    premium,
    profile,
    qimen,
    liuren,
    taiyi,
    reports,
    shares,
    stash,
    ziwei,
)

# 统一前缀 /api：后端部署为「独立 Vercel 项目」时，Vercel 把 /api/* 路由到 api/index.py
# 并把完整路径（含 /api）交给本应用。因此本前缀必须保持 /api —— 不要改成 "" 或 "/"，
# 也不要在前端 base 里再加 /api，否则会出现双 /api 或 404。
api_router = APIRouter(prefix="/api")

# 健康检查挂 API 根级（不随业务版本变化）：/api/health
api_router.include_router(health.router)

# v1 业务路由：/api/v1/*
api_router.include_router(auth.router, prefix="/v1")
api_router.include_router(profile.router, prefix="/v1")
api_router.include_router(ping.router, prefix="/v1")
api_router.include_router(numerology.router, prefix="/v1")
api_router.include_router(ming.router, prefix="/v1")
api_router.include_router(bazi.router, prefix="/v1")
api_router.include_router(ziwei.router, prefix="/v1")
api_router.include_router(gua.router, prefix="/v1")
api_router.include_router(qimen.router, prefix="/v1")
# 三式补齐（P2-1 / P2-2）：大六壬 / 太乙神数，与既有奇门共用 PaipanRequest 入参
api_router.include_router(liuren.router, prefix="/v1")
api_router.include_router(taiyi.router, prefix="/v1")
api_router.include_router(reports.router, prefix="/v1")
api_router.include_router(donations.router, prefix="/v1")
api_router.include_router(premium.router, prefix="/v1")
api_router.include_router(shares.router, prefix="/v1")
api_router.include_router(stash.router, prefix="/v1")
api_router.include_router(angel.router, prefix="/v1")
# 社区综合页（/community）：圈子 / 帖子 / 评论 / 点赞 / 公告 / 排行
api_router.include_router(community.router, prefix="/v1")

# 后台管理系统已于 2026-09-09 拆分为**独立服务** oraclemind-admin（端口 8001），
# 不再挂载于此：共享同一数据库，但独立进程、独立鉴权（om_admin_auth），
# 改后台代码重启不再影响占卜主站。

# 后续版本在此追加：api_router.include_router(v2_router, prefix="/v2")
