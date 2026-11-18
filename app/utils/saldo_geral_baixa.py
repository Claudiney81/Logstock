from flask import current_app
from app.models import SaldoTecnico


def titular_saldo_baixa(tecnico_id, tipo_estoque):
    if tipo_estoque == "empresa":
        return current_app.config.get("TECNICO_SALDO_GERAL_ID") or tecnico_id
    return tecnico_id


def descontar_saldo(saldo_id, quantidade):
    return SaldoTecnico.query.filter(
        SaldoTecnico.id == saldo_id,
        SaldoTecnico.quantidade >= quantidade,
    ).update(
        {SaldoTecnico.quantidade: SaldoTecnico.quantidade - quantidade},
        synchronize_session="fetch",
    ) == 1
