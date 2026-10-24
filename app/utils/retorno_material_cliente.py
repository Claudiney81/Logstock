"""Retorno de materiais do saldo cliente do técnico ao estoque do mesmo cliente."""
from sqlalchemy import or_

from app.extensions import db
from app.models import (Empresa, Estoque, Item, MovimentacaoEstoque,
                        MovimentacaoEstoqueItem, OrdemServico, SaldoTecnico, Tecnico)


def registrar_retorno_cliente(tecnico_id, cliente_id, ordem_servico_id,
                              tipo_servico_id, codigos, quantidades,
                              usuario_id, observacao, assinatura=None):
    """Valida o lote inteiro antes de debitar. O chamador confirma a transação."""
    if not Tecnico.query.filter_by(id=tecnico_id).first():
        raise ValueError('Selecione o técnico que fará a devolução.')
    cliente = Empresa.query.filter_by(id=cliente_id, tipo_empresa='cliente').first()
    ordem = OrdemServico.query.filter_by(id=ordem_servico_id, cliente_id=cliente_id).first()
    if not cliente or not ordem:
        raise ValueError('Selecione o cliente de origem e uma O.S. pertencente a ele.')
    if not tipo_servico_id:
        raise ValueError('Selecione o tipo de serviço.')
    tipo_saldo = 1
    if not codigos or len(codigos) != len(quantidades):
        raise ValueError('Informe os materiais e as quantidades para devolver.')

    selecionados = {}
    for codigo, quantidade_raw in zip(codigos, quantidades):
        codigo = (codigo or '').strip()
        if not codigo:
            if (quantidade_raw or '').strip() not in ('', '0'):
                raise ValueError('Selecione o material de cada quantidade informada.')
            continue
        if codigo in selecionados:
            raise ValueError('Remova os materiais repetidos antes de devolver.')
        if not str(quantidade_raw).isascii() or not str(quantidade_raw).isdigit():
            raise ValueError('Informe quantidades inteiras e positivas para devolver.')
        quantidade = int(quantidade_raw)
        if quantidade <= 0 or quantidade > 999999999:
            raise ValueError('Informe quantidades inteiras e positivas para devolver.')
        item = Item.query.filter_by(codigo=codigo, categoria='MATERIAL').first()
        if not item:
            raise ValueError(f'Material inválido para devolução: {codigo}.')
        selecionados[codigo] = (item, quantidade)
    if not selecionados:
        raise ValueError('Selecione pelo menos um material para devolver.')

    ids = [item.id for item, _ in selecionados.values()]
    saldos = SaldoTecnico.query.filter(
        SaldoTecnico.tecnico_id == tecnico_id,
        SaldoTecnico.tipo_estoque == 'cliente',
        SaldoTecnico.cliente_id == cliente_id,
        SaldoTecnico.ordem_servico_id == ordem_servico_id,
        SaldoTecnico.tipo_servico_id == tipo_saldo,
        SaldoTecnico.item_id.in_(ids),
        SaldoTecnico.quantidade > 0,
    ).order_by(SaldoTecnico.id).populate_existing().with_for_update().all()
    estoques = Estoque.query.filter(
        Estoque.tipo_estoque == 'cliente', Estoque.cliente_id == cliente_id,
        Estoque.tipo_servico_id == tipo_saldo, Estoque.item_id.in_(ids),
        or_(Estoque.condicao_material.is_(None), Estoque.condicao_material == ''),
    ).order_by(Estoque.id).populate_existing().with_for_update().all()

    planos = []
    for item, quantidade in selecionados.values():
        registros = [s for s in saldos if s.item_id == item.id]
        if sum(s.quantidade for s in registros) < quantidade:
            raise ValueError(f'Saldo insuficiente do técnico no cliente/O.S. para o item {item.codigo}. Nenhum item foi devolvido.')
        destinos = [e for e in estoques if e.item_id == item.id]
        if len(destinos) > 1:
            raise ValueError(f'Estoque cliente duplicado para {item.codigo}. Confira antes de devolver.')
        planos.append((item, quantidade, registros, destinos[0] if destinos else None))

    movimentacao = MovimentacaoEstoque(
        origem_tipo='tecnico', origem_id=tecnico_id,
        destino_tipo='cliente', destino_id=cliente_id,
        tipo_servico_id=tipo_servico_id, ordem_servico_id=ordem_servico_id,
        categoria_movimentacao='MATERIAL', tipo_movimentacao='retorno_cliente',
        motivo_retorno='devolucao', observacao=observacao,
        usuario_id=usuario_id, assinatura=assinatura, assinado_por='logistica',
    )
    db.session.add(movimentacao)
    for item, quantidade, registros, destino in planos:
        restante, valor_total = quantidade, 0
        for saldo in registros:
            retirada = min(saldo.quantidade, restante)
            anterior = saldo.quantidade
            alterados = SaldoTecnico.query.filter_by(id=saldo.id, quantidade=anterior).update(
                {SaldoTecnico.quantidade: SaldoTecnico.quantidade - retirada},
                synchronize_session=False,
            )
            if alterados != 1:
                raise ValueError('O saldo foi alterado por outra operação. Reabra a devolução.')
            valor_total += retirada * float(saldo.valor_unitario or 0)
            restante -= retirada
            if not restante:
                break
        valor_unitario = valor_total / quantidade
        if destino:
            Estoque.query.filter_by(id=destino.id).update(
                {Estoque.quantidade: db.func.coalesce(Estoque.quantidade, 0) + quantidade},
                synchronize_session=False,
            )
        else:
            db.session.add(Estoque(
                item_id=item.id, tipo_servico_id=tipo_saldo,
                tipo_estoque='cliente', cliente_id=cliente_id,
                quantidade=quantidade, quantidade_minima=0,
                valor_unitario=valor_unitario, endereco='',
            ))
        movimentacao.itens.append(MovimentacaoEstoqueItem(
            item_id=item.id, quantidade=quantidade, valor_unitario=valor_unitario,
        ))
    return movimentacao
