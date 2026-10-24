"""Correções de notas com validação de saldo e histórico de alterações."""
import hashlib
import json
from collections import defaultdict

from flask import current_app
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy import and_, or_

from app.extensions import db
from app.models import (Empresa, Estoque, MovimentacaoEstoque, MovimentacaoEstoqueItem,
                        RequisicaoTecnico, RequisicaoTecnicoItem, SaldoTecnico)


def retrato(nota):
    return {
        'id': nota.id, 'numero_nf': nota.numero_nf, 'fornecedor': nota.fornecedor,
        'observacao': nota.observacao or '', 'tipo_estoque': nota.tipo_estoque,
        'data_recebimento': nota.data_recebimento.isoformat() if nota.data_recebimento else None,
        'cliente_id': nota.cliente_id, 'tipo_servico_id': nota.tipo_servico_id,
        'cliente_nome': nota.cliente.razao_social if nota.cliente else None,
        'ordem_servico_id': nota.ordem_servico_id,
        'itens': [{'id': i.id, 'item_id': i.item_id, 'quantidade': i.quantidade,
                   'valor_unitario': i.valor_unitario}
                  for i in sorted(nota.itens, key=lambda i: i.id)],
    }


def assinatura(nota):
    digest = hashlib.sha256(json.dumps(retrato(nota), sort_keys=True).encode()).hexdigest()
    return URLSafeSerializer(current_app.secret_key, salt='editar-nota').dumps(digest)


def conferir_assinatura(nota, token):
    try:
        serializer = URLSafeSerializer(current_app.secret_key, salt='editar-nota')
        return serializer.loads(token) == serializer.loads(assinatura(nota))
    except BadSignature:
        return False


def bloqueio_quantidades(nota):
    """Conservative when entries share stock: refuse ambiguous movement history."""
    ids = [i.item_id for i in nota.itens]
    codigos = [i.item.codigo for i in nota.itens if i.item]
    if not ids or any(not i.item for i in nota.itens):
        return 'Nota sem itens válidos para correção de quantidade.'
    if any((i.item.categoria or '').upper() in ('FERRAMENTA', 'EPI') for i in nota.itens):
        return 'A correção de quantidades está disponível apenas para materiais.'
    # A movement may not identify its invoice (company stock and older records).
    # No date cutoff: requisition timestamps do not track actual delivery time.
    mesma_origem = MovimentacaoEstoque.origem_tipo == nota.tipo_estoque
    if nota.tipo_estoque == 'cliente':
        mesma_origem = and_(mesma_origem, or_(MovimentacaoEstoque.origem_id == nota.cliente_id,
                                             MovimentacaoEstoque.origem_id.is_(None)))
    movimentada = db.session.query(MovimentacaoEstoque.id).join(MovimentacaoEstoqueItem).filter(
        MovimentacaoEstoqueItem.item_id.in_(ids),
        or_(MovimentacaoEstoque.nota_fiscal_id == nota.id,
            mesma_origem),
    ).first()
    requisicoes = db.session.query(RequisicaoTecnico.id).join(RequisicaoTecnicoItem).filter(
        RequisicaoTecnico.tipo_estoque == nota.tipo_estoque,
        RequisicaoTecnicoItem.codigo.in_(codigos),
    )
    if nota.tipo_estoque == 'cliente':
        requisicoes = requisicoes.filter(RequisicaoTecnico.cliente_id == nota.cliente_id)
    requisitada = requisicoes.first()
    saldo_tecnico = SaldoTecnico.query.filter(
        SaldoTecnico.item_id.in_(ids), SaldoTecnico.tipo_estoque == nota.tipo_estoque,
        SaldoTecnico.quantidade > 0,
    )
    if nota.tipo_estoque == 'cliente':
        saldo_tecnico = saldo_tecnico.filter(SaldoTecnico.cliente_id == nota.cliente_id)
    if movimentada or requisitada or saldo_tecnico.first():
        return ('Quantidade bloqueada: há movimentação, requisição ou saldo técnico para '
                'os materiais desta origem. Não é possível garantir que a entrada esteja intacta.')
    return None


def ajustar_quantidades(nota, quantidades):
    # Lock in a stable order before checking movements; transfer paths use the
    # same row locks and must read the corrected balance after waiting.
    Estoque.query.filter(
        Estoque.item_id.in_([i.item_id for i in nota.itens]),
        Estoque.tipo_estoque == nota.tipo_estoque,
        Estoque.cliente_id == (nota.cliente_id if nota.tipo_estoque == 'cliente' else None),
    ).order_by(Estoque.id).populate_existing().with_for_update().all()
    bloqueio = bloqueio_quantidades(nota)
    if bloqueio:
        raise ValueError(bloqueio)
    diferencas = defaultdict(int)
    for item in nota.itens:
        diferencas[item.item_id] += quantidades[item.id] - item.quantidade
    for item_id in sorted(diferencas):
        delta = diferencas[item_id]
        if not delta:
            continue
        saldos = Estoque.query.filter_by(
            item_id=item_id, tipo_estoque=nota.tipo_estoque,
            cliente_id=nota.cliente_id if nota.tipo_estoque == 'cliente' else None,
            tipo_servico_id=1 if nota.tipo_servico_id else None,
        ).order_by(Estoque.id).with_for_update().all()
        if len(saldos) != 1:
            raise ValueError('Estoque ausente ou com registros duplicados. Correção bloqueada para conferência.')
        saldo = saldos[0]
        anterior = saldo.quantidade or 0
        if anterior + delta < 0:
            raise ValueError('Saldo insuficiente para retirar a quantidade lançada a mais.')
        # Conditional write also catches a stock change between reading and writing.
        alterados = Estoque.query.filter_by(id=saldo.id, quantidade=anterior).update(
            {Estoque.quantidade: Estoque.quantidade + delta}, synchronize_session=False)
        if alterados != 1:
            raise ValueError('O estoque foi alterado por outra operação. Reabra a nota.')
    for item in nota.itens:
        item.quantidade = quantidades[item.id]


def corrigir_cliente(nota, novo_cliente_id, quantidades, confirmado):
    """Transfere exatamente a entrada da nota, preservando os demais saldos."""
    if nota.tipo_estoque != 'cliente' or not nota.cliente_id:
        raise ValueError('A troca de cliente está disponível apenas para notas do estoque cliente.')
    if any(quantidades[i.id] != i.quantidade for i in nota.itens):
        raise ValueError('Na troca de cliente, as quantidades devem ser exatamente as lançadas na nota. Não é permitido aumentar ou reduzir.')
    if not confirmado:
        raise ValueError('Confira os materiais e confirme as quantidades da nota antes de trocar o cliente.')
    cliente = Empresa.query.filter_by(id=novo_cliente_id, tipo_empresa='cliente').first()
    if not cliente:
        raise ValueError('Selecione um cliente válido para o novo destino.')
    if novo_cliente_id == nota.cliente_id:
        raise ValueError('Selecione um cliente diferente do atual.')
    if nota.ordem_servico_id:
        raise ValueError('Esta nota está vinculada a uma O.S. Confira o vínculo antes de corrigir o cliente.')

    quantidades_por_item = defaultdict(int)
    for item in nota.itens:
        if int(item.quantidade or 0) <= 0:
            raise ValueError('A nota contém quantidade inválida. Confira os itens antes de corrigir o cliente.')
        quantidades_por_item[item.item_id] += item.quantidade
    saldos = Estoque.query.filter(
        Estoque.item_id.in_(quantidades_por_item),
        Estoque.tipo_estoque == 'cliente',
        Estoque.cliente_id.in_([nota.cliente_id, novo_cliente_id]),
        Estoque.tipo_servico_id == (1 if nota.tipo_servico_id else None),
    ).order_by(Estoque.id).populate_existing().with_for_update().all()
    bloqueio = bloqueio_quantidades(nota)
    if bloqueio:
        raise ValueError(bloqueio)

    for item_id, quantidade in sorted(quantidades_por_item.items()):
        origem = [s for s in saldos if s.item_id == item_id and s.cliente_id == nota.cliente_id]
        destino = [s for s in saldos if s.item_id == item_id and s.cliente_id == novo_cliente_id]
        if len(origem) != 1 or len(destino) > 1:
            raise ValueError('Estoque ausente ou duplicado. Correção bloqueada para conferência.')
        anterior = origem[0].quantidade or 0
        if anterior < quantidade:
            raise ValueError('Saldo insuficiente no cliente anterior para retirar a quantidade integral da nota.')
        if any(s.condicao_material not in (None, '', 'DISPONIVEL') for s in origem + destino):
            raise ValueError('Material com condição especial. Correção bloqueada para conferência.')
        alterados = Estoque.query.filter_by(id=origem[0].id, quantidade=anterior).update(
            {Estoque.quantidade: Estoque.quantidade - quantidade}, synchronize_session=False)
        if alterados != 1:
            raise ValueError('O estoque foi alterado por outra operação. Reabra a nota.')
        if destino:
            saldo_destino = destino[0]
            alterados = Estoque.query.filter_by(id=saldo_destino.id, quantidade=saldo_destino.quantidade).update(
                {Estoque.quantidade: Estoque.quantidade + quantidade}, synchronize_session=False)
            if alterados != 1:
                raise ValueError('O estoque de destino foi alterado. Reabra a nota.')
        else:
            db.session.add(Estoque(
                item_id=item_id, tipo_servico_id=origem[0].tipo_servico_id,
                tipo_estoque='cliente', cliente_id=novo_cliente_id,
                quantidade=quantidade, quantidade_minima=0, endereco='',
                valor_unitario=origem[0].valor_unitario,
                condicao_material=origem[0].condicao_material,
            ))
    nota.cliente = cliente
