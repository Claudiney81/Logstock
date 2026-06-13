"""add valor_unitario to estoque and saldo_tecnico

Revision ID: c6f4d2a91b7e
Revises: 480f88d76151
Create Date: 2026-06-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c6f4d2a91b7e'
down_revision = '480f88d76151'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())

    estoque_cols = [col['name'] for col in inspector.get_columns('estoque')]
    if 'valor_unitario' not in estoque_cols:
        with op.batch_alter_table('estoque', schema=None) as batch_op:
            batch_op.add_column(sa.Column('valor_unitario', sa.Float(), nullable=True))

    saldo_cols = [col['name'] for col in inspector.get_columns('saldo_tecnico')]
    if 'valor_unitario' not in saldo_cols:
        with op.batch_alter_table('saldo_tecnico', schema=None) as batch_op:
            batch_op.add_column(sa.Column('valor_unitario', sa.Float(), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())

    saldo_cols = [col['name'] for col in inspector.get_columns('saldo_tecnico')]
    if 'valor_unitario' in saldo_cols:
        with op.batch_alter_table('saldo_tecnico', schema=None) as batch_op:
            batch_op.drop_column('valor_unitario')

    estoque_cols = [col['name'] for col in inspector.get_columns('estoque')]
    if 'valor_unitario' in estoque_cols:
        with op.batch_alter_table('estoque', schema=None) as batch_op:
            batch_op.drop_column('valor_unitario')
