"""scale attempts: 量表作答持久化（右轨心理学产品）

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-09-20 10:00:00.000000

对应双轨右轨 MVP 待办①：
- 新增 scale_attempts 表，留存每次量表作答（answers_json）+ 服务端计分结果
  （score_json）+ 综合摘要（summary），供 AI 心理报告直接取服务端计分、也为
  个人中心「查看 / 删除」提供真源；
- 归属复用 premium_orders 的 visitor / user 双轨（slug / user_id / visitor_id 索引）。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scale_attempts',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False, comment='量表 slug'),
        sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True, comment='登录用户ID'),
        sa.Column('visitor_id', sa.String(length=64), server_default='', nullable=False, comment='访客ID（匿名归属）'),
        sa.Column('owner_type', sa.String(length=8), server_default='visitor', nullable=False, comment='归属：user / visitor / anonymous'),
        sa.Column('answers_json', sa.JSON(), nullable=False, comment='作答：{题ID: 1-5}'),
        sa.Column('score_json', sa.JSON(), nullable=False, comment='计分结果：维度分列表'),
        sa.Column('summary', sa.Text(), server_default='', nullable=False, comment='综合觉察摘要'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id'),
    )
    with op.batch_alter_table('scale_attempts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_scale_attempts_slug'), ['slug'], unique=False)
        batch_op.create_index(batch_op.f('ix_scale_attempts_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_scale_attempts_visitor_id'), ['visitor_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('scale_attempts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_scale_attempts_visitor_id'))
        batch_op.drop_index(batch_op.f('ix_scale_attempts_user_id'))
        batch_op.drop_index(batch_op.f('ix_scale_attempts_slug'))
    op.drop_table('scale_attempts')
