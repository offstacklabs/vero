"""Add users and audit logs tables for enterprise authentication and RBAC

Revision ID: 003_add_users_and_auth
Revises: 002_add_telemetry_cost
Create Date: 2026-10-10 12:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_add_users_and_auth'
down_revision: Union[str, None] = '002_add_telemetry_cost'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Users table
    if '_vero_users' not in existing_tables:
        op.create_table(
            '_vero_users',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('email', sa.String(length=256), nullable=False, unique=True),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('password_hash', sa.String(length=256), nullable=True),
            sa.Column('api_key_hash', sa.String(length=128), nullable=True),
            sa.Column('role', sa.String(length=32), nullable=False, server_default='analyst'),
            sa.Column('allowed_domains', sa.Text(), nullable=False, server_default='["*"]'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('last_login_at', sa.DateTime(), nullable=True)
        )

    # 2. Audit logs table
    if '_vero_audit_logs' not in existing_tables:
        op.create_table(
            '_vero_audit_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column('user_id', sa.String(length=64), nullable=True),
            sa.Column('user_email', sa.String(length=256), nullable=True),
            sa.Column('action', sa.String(length=64), nullable=False),
            sa.Column('domain', sa.String(length=64), nullable=True),
            sa.Column('details_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True)
        )

def downgrade() -> None:
    op.drop_table('_vero_audit_logs')
    op.drop_table('_vero_users')
