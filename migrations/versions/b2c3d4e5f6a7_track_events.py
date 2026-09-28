"""track events: P0 漏斗埋点事件表（占卜→心理付费转化追踪）

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-20 15:30:00.000000

对应 P0 漏斗：卜卦/塔罗解读完成后，把"刚说出口的困扰"接到情绪打卡 + 复原力测评。
track_events 记录匿名漏斗事件（bridge_exposure / bridge_mood_submit /
bridge_assessment_click / assessment_paid），由主站建表，admin 后端只读共享。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'track_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False, comment='事件类型'),
        sa.Column('source', sa.String(length=32), nullable=False, comment='入口来源：bugua / tarot'),
        sa.Column('visitor_id', sa.String(length=64), nullable=False, comment='访客ID（匿名归因）'),
        sa.Column('props', sa.JSON(), nullable=True, comment='附加属性，如 mood / score'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('track_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_track_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_track_events_source'), ['source'], unique=False)
        batch_op.create_index(batch_op.f('ix_track_events_visitor_id'), ['visitor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_track_events_created_at'), ['created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('track_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_track_events_created_at'))
        batch_op.drop_index(batch_op.f('ix_track_events_visitor_id'))
        batch_op.drop_index(batch_op.f('ix_track_events_source'))
        batch_op.drop_index(batch_op.f('ix_track_events_event_type'))
    op.drop_table('track_events')
