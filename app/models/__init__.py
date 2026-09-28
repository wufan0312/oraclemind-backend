"""ORM 模型注册中心。

新模型定义后在此 import 一次，确保 Base.metadata 收集到全部表，
供建表脚本 / alembic 自动生成迁移使用。

规划表（tech_stack_plan §5）：
- 用户域：users / user_profiles / memberships / cultivation_scores
- 排盘域：divination_records / ai_interpretations / comprehensive_reports
- 互动域：dream_diaries / mood_records / xuan_conversations / wudao_records
- 支付域：orders / payments

已落地：
- 排盘域：reports（comprehensive_reports 的简化实现，见 app/models/report.py）
- 排盘域增强：report_annotations（报告批注）
- 支付域：donation_orders（随喜供养订单，渠道可插拔）
- 支付域：premium_orders（进阶内容付费订单，带商品标识，渠道可插拔）
"""

from app.models.approval import Approval
from app.models.audit import AuditLog
# 注：admins / admin_audit_logs 已随后台管理系统拆分为独立服务 oraclemind-admin，
# 模型定义不再注册于此（表仍在同一数据库，由后台服务与既有 Alembic 迁移维护）。
from app.models.community import (
    CommunityCircle,
    CommunityPost,
    CommunityComment,
    CommunityLike,
    CommunityAnnouncement,
)
from app.models.donation_order import DonationOrder
from app.models.premium_order import PremiumOrder
from app.models.report import Report
from app.models.report_annotation import ReportAnnotation
from app.models.scale_attempt import ScaleAttempt
from app.models.schema_migration import SchemaMigration
from app.models.track_event import TrackEvent
from app.models.share import Share
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.user_stash import UserStash

__all__ = [
    "Approval",
    "AuditLog",
    "CommunityCircle",
    "CommunityPost",
    "CommunityComment",
    "CommunityLike",
    "CommunityAnnouncement",
    "DonationOrder",
    "PremiumOrder",
    "Report",
    "ReportAnnotation",
    "ScaleAttempt",
    "SchemaMigration",
    "TrackEvent",
    "Share",
    "User",
    "UserProfile",
    "UserStash",
]
