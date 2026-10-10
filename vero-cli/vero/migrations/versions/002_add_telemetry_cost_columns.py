"""Add telemetry bytes_scanned and cost_usd columns to query runs

Revision ID: 002_add_telemetry_cost
Revises: 001_initial_schema
Create Date: 2026-10-10 11:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_add_telemetry_cost'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns('_vero_query_runs')]

    with op.batch_alter_table('_vero_query_runs') as batch_op:
        if 'bytes_scanned' not in cols:
            batch_op.add_column(sa.Column('bytes_scanned', sa.BigInteger(), nullable=True, server_default='0'))
        if 'cost_usd' not in cols:
            batch_op.add_column(sa.Column('cost_usd', sa.Float(), nullable=True, server_default='0.0'))

def downgrade() -> None:
    with op.batch_alter_table('_vero_query_runs') as batch_op:
        batch_op.drop_column('cost_usd')
        batch_op.drop_column('bytes_scanned')
