from app.extensions import db
from app.models import (
    MovimentacaoEstoque,
    MovimentacaoEstoqueItem,
    OrdemServico,
    SaldoTecnico
)


def transferir_sobras_cliente_para_empresa(tecnico_id, ordem_servico_id):
    if not tecnico_id or not ordem_servico_id:
        return 0

    saldos_cliente = (
        SaldoTecnico.query
        .filter(
            SaldoTecnico.tecnico_id == tecnico_id,
            SaldoTecnico.ordem_servico_id == ordem_servico_id,
            db.func.lower(SaldoTecnico.tipo_estoque) == "cliente",
            SaldoTecnico.quantidade > 0
        )
        .all()
    )

    if not saldos_cliente:
        return 0

    ordem = OrdemServico.query.get(ordem_servico_id)
    quantidade_transferida = 0
    movimentacao = MovimentacaoEstoque(
        origem_tipo="cliente",
        origem_id=ordem.cliente_id if ordem else None,
        destino_tipo="tecnico",
        destino_id=tecnico_id,
        tipo_servico_id=1,
        ordem_servico_id=ordem_servico_id,
        categoria_movimentacao="MATERIAL",
        tipo_movimentacao="retorno_sobra_os",
        motivo_retorno="Sobra transferida automaticamente no fechamento da O.S",
        observacao=(
            "Transferencia automatica da sobra do saldo cliente/O.S "
            "para o saldo empresa do tecnico."
        )
    )
    db.session.add(movimentacao)
    db.session.flush()

    for saldo_cliente in saldos_cliente:
        quantidade = int(saldo_cliente.quantidade or 0)

        if quantidade <= 0:
            continue

        saldo_empresa = (
            SaldoTecnico.query
            .filter_by(
                tecnico_id=tecnico_id,
                item_id=saldo_cliente.item_id,
                tipo_servico_id=saldo_cliente.tipo_servico_id or 1,
                tipo_estoque="empresa",
                cliente_id=None,
                ordem_servico_id=None
            )
            .first()
        )

        if saldo_empresa:
            saldo_empresa.quantidade = int(saldo_empresa.quantidade or 0) + quantidade

            if saldo_cliente.valor_unitario is not None:
                saldo_empresa.valor_unitario = saldo_cliente.valor_unitario

        else:
            db.session.add(
                SaldoTecnico(
                    tecnico_id=tecnico_id,
                    item_id=saldo_cliente.item_id,
                    tipo_servico_id=saldo_cliente.tipo_servico_id or 1,
                    quantidade=quantidade,
                    quantidade_minima=0,
                    valor_unitario=saldo_cliente.valor_unitario,
                    tipo_estoque="empresa",
                    cliente_id=None,
                    ordem_servico_id=None,
                    endereco="",
                    bairro="",
                    codigo_imovel=""
                )
            )

        db.session.add(
            MovimentacaoEstoqueItem(
                movimentacao_id=movimentacao.id,
                item_id=saldo_cliente.item_id,
                quantidade=quantidade,
                valor_unitario=float(saldo_cliente.valor_unitario or 0)
            )
        )

        saldo_cliente.quantidade = 0
        quantidade_transferida += quantidade

    return quantidade_transferida
