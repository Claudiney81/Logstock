from app import db
from app.models import Estoque, SaldoTecnico


def sincronizar_valor_empresa_item(item_id, valor_unitario):
    """Atualiza saldos abertos de origem empresa para o valor corrente do item."""
    valor = float(valor_unitario or 0)

    Estoque.query.filter(
        Estoque.item_id == item_id,
        Estoque.tipo_estoque == 'empresa'
    ).update(
        {Estoque.valor_unitario: valor},
        synchronize_session=False
    )

    SaldoTecnico.query.filter(
        SaldoTecnico.item_id == item_id,
        SaldoTecnico.tipo_estoque == 'empresa'
    ).update(
        {SaldoTecnico.valor_unitario: valor},
        synchronize_session=False
    )
