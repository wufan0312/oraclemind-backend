"""report enhancements: favorite/pin/version + annotations + donation orders

Revision ID: c7e1a9b3d452
Revises: 48b6c8479c7d
Create Date: 2026-09-09 16:20:00.000000

对应《报告页面功能缺失分析》：
- #5 收藏/置顶：reports 新增 favorited / pinned
- #7 批量删除：复用软删，无 schema 变更
- #8 个人批注：新增 report_annotations 表
- #12 版本管理：reports 新增 parent_id / variant
- #1 随喜供养：新增 donation_orders 表（渠道可插拔）
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e1a9b3d452'
down_revision = '48b6c8479c7d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- reports：收藏 / 置顶 / 版本链 ---
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('favorited', sa.Boolean(), server_default='0', nullable=False,
                                      comment='是否收藏（收藏项在列表中可单独筛选，并默认排在前面）'))
        batch_op.add_column(sa.Column('pinned', sa.Boolean(), server_default='0', nullable=False,
                                     comment='是否置顶（置顶项永远排在最前，优先于收藏）'))
        batch_op.add_column(sa.Column('parent_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                                      nullable=True, comment='父报告ID：「换个说法」产生的版本链，根版本为 NULL'))
        batch_op.add_column(sa.Column('variant', sa.Integer(), server_default='0', nullable=False,
                                      comment='版本号：根版本 0，「换个说法」第 N 次为 N'))
        batch_op.create_index(batch_op.f('ix_reports_parent_id'), ['parent_id'], unique=False)

    # --- report_annotations：报告个人批注 ---
    op.create_table(
        'report_annotations',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('report_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False,
                  comment='所属报告ID（reports.id，软删报告保留历史批注）'),
        sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True, comment='登录用户ID'),
        sa.Column('visitor_id', sa.String(length=64), server_default='', nullable=False, comment='访客ID（匿名批注归属）'),
        sa.Column('owner_type', sa.String(length=8), server_default='visitor', nullable=False, comment='归属：visitor / user'),
        sa.Column('anchor', sa.String(length=64), server_default='', nullable=False,
                  comment='锚点：报告内区块标识（summary / cards.1 / dims.事业 / timeline.0），空=整篇'),
        sa.Column('anchor_label', sa.String(length=128), server_default='', nullable=False, comment='锚点展示名'),
        sa.Column('quote', sa.String(length=512), server_default='', nullable=False, comment='被批注的原文片段'),
        sa.Column('content', sa.Text(), server_default='', nullable=False, comment='批注正文'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('report_annotations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_report_annotations_report_id'), ['report_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_report_annotations_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_report_annotations_visitor_id'), ['visitor_id'], unique=False)

    # --- donation_orders：随喜供养订单 ---
    op.create_table(
        'donation_orders',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('out_trade_no', sa.String(length=64), nullable=False, comment='商户订单号（幂等键）'),
        sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True, comment='登录用户ID'),
        sa.Column('visitor_id', sa.String(length=64), server_default='', nullable=False, comment='访客ID（匿名供养归属）'),
        sa.Column('owner_type', sa.String(length=8), server_default='visitor', nullable=False, comment='归属：visitor / user'),
        sa.Column('amount_fen', sa.Integer(), nullable=False, comment='供养金额（单位：分）'),
        sa.Column('tier', sa.String(length=32), server_default='', nullable=False, comment='档位名：心意 / 诚意 / 大愿 / 自定义'),
        sa.Column('channel', sa.String(length=16), server_default='stub', nullable=False, comment='支付渠道：wechat / stub'),
        sa.Column('status', sa.String(length=16), server_default='pending', nullable=False,
                  comment='订单状态：pending / paid / failed / expired'),
        sa.Column('pay_url', sa.String(length=1024), nullable=True, comment='收款码/支付链接'),
        sa.Column('transaction_id', sa.String(length=128), nullable=True, comment='渠道交易号'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True, comment='支付完成时间'),
        sa.Column('expire_at', sa.DateTime(timezone=True), nullable=False, comment='订单过期时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('out_trade_no'),
    )
    with op.batch_alter_table('donation_orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_donation_orders_out_trade_no'), ['out_trade_no'], unique=True)
        batch_op.create_index(batch_op.f('ix_donation_orders_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_donation_orders_visitor_id'), ['visitor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_donation_orders_status'), ['status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('donation_orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_donation_orders_status'))
        batch_op.drop_index(batch_op.f('ix_donation_orders_visitor_id'))
        batch_op.drop_index(batch_op.f('ix_donation_orders_user_id'))
        batch_op.drop_index(batch_op.f('ix_donation_orders_out_trade_no'))
    op.drop_table('donation_orders')

    with op.batch_alter_table('report_annotations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_report_annotations_visitor_id'))
        batch_op.drop_index(batch_op.f('ix_report_annotations_user_id'))
        batch_op.drop_index(batch_op.f('ix_report_annotations_report_id'))
    op.drop_table('report_annotations')

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reports_parent_id'))
        batch_op.drop_column('variant')
        batch_op.drop_column('parent_id')
        batch_op.drop_column('pinned')
        batch_op.drop_column('favorited')
