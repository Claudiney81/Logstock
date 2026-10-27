"""Audit restricted invoice corrections.

Revision ID: d7e52a8c104b
Revises: c6f4d2a91b7e
"""
from alembic import op
import sqlalchemy as sa

revision = 'd7e52a8c104b'
down_revision = 'c6f4d2a91b7e'
branch_labels = None
depends_on = None


def upgrade():
    # Application startup also uses create_all; support both upgrade paths.
    if not sa.inspect(op.get_bind()).has_table('notas_fiscais_edicoes'):
        op.create_table(
            'notas_fiscais_edicoes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('nota_fiscal_id', sa.Integer(), sa.ForeignKey('notas_fiscais_entrada.id'), nullable=False),
            sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
            sa.Column('data_hora', sa.DateTime(), nullable=False),
            sa.Column('motivo', sa.Text(), nullable=False),
            sa.Column('antes', sa.JSON(), nullable=False),
            sa.Column('depois', sa.JSON(), nullable=False),
        )
        op.create_index('ix_notas_fiscais_edicoes_nota_fiscal_id', 'notas_fiscais_edicoes', ['nota_fiscal_id'])


def downgrade():
    op.drop_table('notas_fiscais_edicoes')
