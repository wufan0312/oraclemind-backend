"""admin system: admins + admin_audit_logs + users ban columns + seed super admin

Revision ID: d2a1f3c5e6b7
Revises: c7e1a9b3d452
Create Date: 2026-09-09 18:40:00.000000
"""
from alembic import op
import sqlalchemy as sa

from passlib.context import CryptContext

# revision identifiers, used by Alembic.
revision = 'd2a1f3c5e6b7'
down_revision = 'c7e1a9b3d452'
branch_labels = None
depends_on = None

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# 默认超管（上线后请立即修改密码）
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Admin@2026"


def upgrade() -> None:
    # admins 表
    op.create_table(
        'admins',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False, comment='管理员用户名'),
        sa.Column('password_hash', sa.String(length=255), nullable=False, comment='密码哈希（pbkdf2_sha256）'),
        sa.Column('role', sa.String(length=20), server_default='viewer', nullable=False, comment='角色：super_admin / operator / viewer'),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False, comment='是否启用'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), onupdate=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_admins_username'), ['username'], unique=True)

    # admin_audit_logs 表
    op.create_table(
        'admin_audit_logs',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('admin_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False, comment='操作管理员 ID'),
        sa.Column('action', sa.String(length=64), nullable=False, comment='动作类型'),
        sa.Column('target_type', sa.String(length=32), nullable=True, comment='对象类型'),
        sa.Column('target_id', sa.String(length=64), nullable=True, comment='对象 ID'),
        sa.Column('detail', sa.JSON(), nullable=True, comment='操作上下文快照'),
        sa.Column('ip', sa.String(length=45), nullable=True, comment='操作 IP'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='SET NULL'),
    )
    with op.batch_alter_table('admin_audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_admin_audit_logs_admin_id'), ['admin_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_admin_audit_logs_action'), ['action'], unique=False)

    # users 表追加封禁字段
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_banned', sa.Boolean(), server_default='0', nullable=False, comment='是否被封禁'))
        batch_op.add_column(sa.Column('banned_reason', sa.String(length=256), nullable=True, comment='封禁原因'))
        batch_op.add_column(sa.Column('banned_at', sa.DateTime(timezone=True), nullable=True, comment='封禁时间'))

    # 种子默认超管（如不存在）
    hashed = pwd_context.hash(DEFAULT_ADMIN_PASSWORD)
    op.execute(
        sa.text(
            "INSERT INTO admins (username, password_hash, role, is_active, created_at, updated_at) "
            "SELECT :username, :pwd, 'super_admin', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
            "WHERE NOT EXISTS (SELECT 1 FROM admins WHERE username = :username)"
        ).bindparams(username=DEFAULT_ADMIN_USERNAME, pwd=hashed)
    )


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('banned_at')
        batch_op.drop_column('banned_reason')
        batch_op.drop_column('is_banned')

    op.drop_table('admin_audit_logs')
    op.drop_table('admins')
