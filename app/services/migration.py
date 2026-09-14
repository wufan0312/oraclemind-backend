"""登录时把访客数据认领到账号（数据存储重设计方案 §三）。

核心：某访客在登录前以 visitor_id 存的报告，登录后应归属到该用户账号，
使其跨设备、跨浏览器都能看到 —— 解决"登录不认账、换设备丢报告"的坑。
"""

from sqlalchemy import update

from app.db.session import async_session
from app.models.report import Report
from app.models.user import User


async def migrate_visitor_reports(user: User, visitor_id: str | None) -> int:
    """把指定 visitor_id 名下、尚未归属任何用户的报告认领到 user（缺陷报告 P1-7）。

    **使用独立的 async_session 提交**，不再复用调用方的请求级 db：
    注册/登录的主事务（写 users + 审计）与认领 UPDATE 事务边界分离，认领失败
    不会回滚账号创建，账号创建失败也不会留下半提交的认领。

    Returns:
        认领的报告条数。
    """
    if not visitor_id:
        return 0
    async with async_session() as db:
        result = await db.execute(
            update(Report)
            .where(Report.visitor_id == visitor_id)
            .where(Report.user_id.is_(None))
            .values(user_id=user.id, owner_type="user")
        )
        await db.commit()
        return result.rowcount or 0
