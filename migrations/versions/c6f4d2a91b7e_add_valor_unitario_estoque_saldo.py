"""add valor_unitario to estoque and saldo_tecnico

Revision ID: c6f4d2a91b7e
Revises: b659a3b9887e
Create Date: 2026-06-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c6f4d2a91b7e'
down_revision = 'b659a3b9887e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('estoque', schema=None) as batch_op:
        batch_op.add_column(sa.Column('valor_unitario', sa.Float(), nullable=True))

    with op.batch_alter_table('saldo_tecnico', schema=None) as batch_op:
        batch_op.add_column(sa.Column('valor_unitario', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('saldo_tecnico', schema=None) as batch_op:
        batch_op.drop_column('valor_unitario')

    with op.batch_alter_table('estoque', schema=None) as batch_op:
        batch_op.drop_column('valor_unitario')
