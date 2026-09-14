"""premium orders: 进阶内容付费订单（付费墙）

Revision ID: e5f3b1a7c904
Revises: d2a1f3c5e6b7
Create Date: 2026-09-10 09:55:00.000000

对应《付费墙占位 · 交付概览》遗留项 #1：
- 新增 premium_orders 表，记录**商品标识 item_id**，解决复用 donation_orders
  时「订单表不记商品、只能按金额对账」的问题；
- 支持生效范围 ref_type / ref_id（单次解锁类商品绑定具体牌局/报告）；
- self_claimed 供个人收款码（无自动回调）人工对账，不参与权益判定。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f3b1a7c904'
down_revision = 'd2a1f3c5e6b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'premium_orders',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('out_trade_no', sa.String(length=64), nullable=False, comment='商户订单号（幂等键）'),
        sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True, comment='登录用户ID'),
        sa.Column('visitor_id', sa.String(length=64), server_default='', nullable=False, comment='访客ID（匿名下单归属）'),
        sa.Column('owner_type', sa.String(length=8), server_default='visitor', nullable=False, comment='归属：visitor / user'),
        sa.Column('item_id', sa.String(length=32), nullable=False, comment='商品ID：tarot_deep / astro_full / all_access'),
        sa.Column('item_name', sa.String(length=64), server_default='', nullable=False, comment='商品名快照（下单时固定）'),
        sa.Column('amount_fen', sa.Integer(), nullable=False, comment='应付金额（单位：分，服务端按目录定价）'),
        sa.Column('ref_type', sa.String(length=32), server_default='', nullable=False, comment='关联对象类型：tarot_spread / report / horoscope'),
        sa.Column('ref_id', sa.String(length=64), server_default='', nullable=False, comment='关联对象ID（如这一局的牌面ID/报告ID）'),
        sa.Column('channel', sa.String(length=16), server_default='stub', nullable=False, comment='支付渠道：wechat / stub'),
        sa.Column('status', sa.String(length=16), server_default='pending', nullable=False,
                  comment='订单状态：pending / paid / failed / expired'),
        sa.Column('pay_url', sa.String(length=1024), nullable=True, comment='收款码/支付链接（stub 渠道为空）'),
        sa.Column('transaction_id', sa.String(length=128), nullable=True, comment='渠道交易号'),
        sa.Column('self_claimed', sa.Boolean(), server_default='0', nullable=False,
                  comment='用户是否自报已付（个人收款码人工对账用，不视为已支付）'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True, comment='支付完成时间'),
        sa.Column('expire_at', sa.DateTime(timezone=True), nullable=False, comment='订单过期时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('out_trade_no'),
    )
    with op.batch_alter_table('premium_orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_premium_orders_out_trade_no'), ['out_trade_no'], unique=True)
        batch_op.create_index(batch_op.f('ix_premium_orders_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_premium_orders_visitor_id'), ['visitor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_premium_orders_item_id'), ['item_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_premium_orders_status'), ['status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('premium_orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_premium_orders_status'))
        batch_op.drop_index(batch_op.f('ix_premium_orders_item_id'))
        batch_op.drop_index(batch_op.f('ix_premium_orders_visitor_id'))
        batch_op.drop_index(batch_op.f('ix_premium_orders_user_id'))
        batch_op.drop_index(batch_op.f('ix_premium_orders_out_trade_no'))
    op.drop_table('premium_orders')
