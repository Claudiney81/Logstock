"""add assinatura_base64 em KitInicial"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "480f88d76151"
down_revision = "ad493b11a123"  # mantenha o seu valor
branch_labels = None
depends_on = None


def upgrade():
    # 1) adiciona colunas com estado seguro
    with op.batch_alter_table("kits_iniciais", schema=None) as batch_op:
        # nova coluna de assinatura (pode ser nula)
        batch_op.add_column(sa.Column("assinatura_base64", sa.Text(), nullable=True))
        # cria 'nome' TEMPORARIAMENTE como nullable para poder popular
        batch_op.add_column(sa.Column("nome", sa.String(length=150), nullable=True))
        # altera tipo de observacao (se já era TEXT)
        batch_op.alter_column(
            "observacao",
            existing_type=sa.Text(),
            type_=sa.String(length=255),
            existing_nullable=True,
        )

    # 2) popular 'nome' a partir de 'nome_kit' (se existir) ou default
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='kits_iniciais' AND column_name='nome_kit'
            ) THEN
                UPDATE kits_iniciais SET nome = COALESCE(nome_kit, 'Kit Inicial');
            ELSE
                UPDATE kits_iniciais SET nome = COALESCE(nome, 'Kit Inicial');
            END IF;
        END$$;
        """
    )

    # 3) agora sim, torna NOT NULL
    with op.batch_alter_table("kits_iniciais", schema=None) as batch_op:
        batch_op.alter_column("nome", nullable=False)

    # 4) remove a antiga 'nome_kit' se existir
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='kits_iniciais' AND column_name='nome_kit'
            ) THEN
                ALTER TABLE kits_iniciais DROP COLUMN nome_kit;
            END IF;
        END$$;
        """
    )


def downgrade():
    # recria nome_kit, copia dados, e desfaz alterações
    with op.batch_alter_table("kits_iniciais", schema=None) as batch_op:
        batch_op.add_column(sa.Column("nome_kit", sa.Text(), nullable=True))

    op.execute("UPDATE kits_iniciais SET nome_kit = nome;")

    with op.batch_alter_table("kits_iniciais", schema=None) as batch_op:
        batch_op.drop_column("nome")
        batch_op.drop_column("assinatura_base64")
        batch_op.alter_column(
            "observacao",
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=True,
        )
