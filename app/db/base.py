"""ORM 声明式基类。

业务模型统一继承 Base，并在 models/__init__.py 中注册，便于 alembic 自动发现。
规划表结构见 tech_stack_plan §5：users / user_profiles / divination_records /
ai_interpretations / comprehensive_reports / orders 等。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
