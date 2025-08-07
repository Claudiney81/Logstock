"""add total_nota manual

Revision ID: 9f1b9923c065
Revises: 764f7aeaf82a
Create Date: 2025-07-27 11:33:55.345738
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9f1b9923c065'
down_revision = '764f7aeaf82a'
branch_labels = None
depends_on = None


def upgrade():
    # Adiciona a coluna total_nota com valor padrão 0
    op.add_column('notas_fiscais_entrada', sa.Column('total_nota', sa.Float(), server_default='0'))


def downgrade():
    # Remove a coluna total_nota caso seja necessário reverter
    op.drop_column('notas_fiscais_entrada', 'total_nota')
