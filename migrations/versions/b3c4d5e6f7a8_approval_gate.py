"""approval gate: 审批 Gate 记录表（P1 Harness 化 · Human-in-the-loop）

Revision ID: b3c4d5e6f7a8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-28 14:00:00.000000

高风险操作（付费/外发/删除）执行副作用前的人工确认留痕：
- 新增 approvals 表，记录 pending→approved/rejected 状态机与 consumed 防重放标记；
- 业务接口凭 approval_id 经 verify_approval 校验后放行，并标记 consumed。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'approvals',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('action_type', sa.String(length=32), nullable=False, comment='动作类型：donation/premium/community_post/share/delete/custom'),
        sa.Column('actor_type', sa.String(length=16), server_default='visitor', nullable=False, comment='操作者类型：user/visitor'),
        sa.Column('actor_id', sa.String(length=64), nullable=True, comment='操作者标识（用户ID或访客ID）'),
        sa.Column('summary', sa.String(length=256), server_default='', nullable=False, comment='展示给用户的确认摘要'),
        sa.Column('payload', sa.JSON(), nullable=True, comment='业务上下文快照（脱敏）'),
        sa.Column('status', sa.String(length=16), server_default='pending', nullable=False, comment='pending/approved/rejected/expired'),
        sa.Column('consumed', sa.Boolean(), server_default='0', nullable=False, comment='是否已被业务消费（防重放）'),
        sa.Column('trace_id', sa.String(length=64), nullable=True, comment='关联 Observability trace'),
        sa.Column('decision_note', sa.String(length=256), nullable=True, comment='审批备注（拒绝原因等）'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True, comment='审批时间'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('approvals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_approvals_action_type'), ['action_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_approvals_actor_id'), ['actor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_approvals_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_approvals_trace_id'), ['trace_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('approvals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_approvals_trace_id'))
        batch_op.drop_index(batch_op.f('ix_approvals_status'))
        batch_op.drop_index(batch_op.f('ix_approvals_actor_id'))
        batch_op.drop_index(batch_op.f('ix_approvals_action_type'))
    op.drop_table('approvals')
