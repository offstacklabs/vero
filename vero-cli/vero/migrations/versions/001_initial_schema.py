"""Initial Vero metadata schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-10 10:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Domains
    if '_vero_domains' not in existing_tables:
        op.create_table(
            '_vero_domains',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('display_name', sa.String(length=128), nullable=False),
            sa.Column('description', sa.Text(), nullable=True)
        )

    # 2. Rules
    if '_vero_rules' not in existing_tables:
        op.create_table(
            '_vero_rules',
            sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column('domain', sa.String(length=64), server_default='global'),
            sa.Column('rule_text', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    # 3. Metrics
    if '_vero_metrics' not in existing_tables:
        op.create_table(
            '_vero_metrics',
            sa.Column('name', sa.String(length=128), primary_key=True),
            sa.Column('domain', sa.String(length=64), primary_key=True, server_default='global'),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('sql', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    # 4. Schemas
    if '_vero_schemas' not in existing_tables:
        op.create_table(
            '_vero_schemas',
            sa.Column('table_name', sa.String(length=128), primary_key=True),
            sa.Column('domain', sa.String(length=64), primary_key=True, server_default='global'),
            sa.Column('markdown', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    # 5. Sessions
    if '_vero_sessions' not in existing_tables:
        op.create_table(
            '_vero_sessions',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('title', sa.String(length=256), nullable=False),
            sa.Column('domain', sa.String(length=64), server_default='global'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    # 6. Messages
    if '_vero_messages' not in existing_tables:
        op.create_table(
            '_vero_messages',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('session_id', sa.String(length=64), nullable=False),
            sa.Column('role', sa.String(length=32), nullable=False),
            sa.Column('text', sa.Text(), nullable=True),
            sa.Column('payload_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True)
        )

    # 7. Query Runs
    if '_vero_query_runs' not in existing_tables:
        op.create_table(
            '_vero_query_runs',
            sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column('sql', sa.Text(), nullable=False),
            sa.Column('duration_ms', sa.Float(), nullable=True),
            sa.Column('row_count', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('executed_at', sa.DateTime(), nullable=True)
        )

    # 8. Dashboard Tiles
    if '_vero_dashboard_tiles' not in existing_tables:
        op.create_table(
            '_vero_dashboard_tiles',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('domain', sa.String(length=64), server_default='global'),
            sa.Column('title', sa.String(length=256), nullable=False),
            sa.Column('tile_type', sa.String(length=32), server_default='chart'),
            sa.Column('chart_type', sa.String(length=32), server_default='bar'),
            sa.Column('sql', sa.Text(), nullable=True),
            sa.Column('data_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True)
        )

def downgrade() -> None:
    op.drop_table('_vero_dashboard_tiles')
    op.drop_table('_vero_query_runs')
    op.drop_table('_vero_messages')
    op.drop_table('_vero_sessions')
    op.drop_table('_vero_schemas')
    op.drop_table('_vero_metrics')
    op.drop_table('_vero_rules')
    op.drop_table('_vero_domains')
