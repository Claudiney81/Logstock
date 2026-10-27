"""Separate physical receipt date from immutable registration timestamp."""
from alembic import op
import sqlalchemy as sa

revision = 'e8a63b9d215c'
down_revision = 'd7e52a8c104b'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'data_recebimento' not in {c['name'] for c in inspector.get_columns('notas_fiscais_entrada')}:
        op.add_column('notas_fiscais_entrada', sa.Column('data_recebimento', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('notas_fiscais_entrada') as table:
        table.drop_column('data_recebimento')
