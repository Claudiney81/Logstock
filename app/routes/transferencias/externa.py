from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from app.extensions import db
from app.models import Empresa, TransferenciaExterna, TransferenciaExternaItem, Item, Estoque, TipoServico
from datetime import datetime

bp_externa = Blueprint('transferencia_externa', __name__, url_prefix='/transferencias/externa')


@bp_externa.route('/')
def nova_transferencia_externa():
    empresas = Empresa.query.order_by(Empresa.razao_social).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    return render_template(
        'transferencias/externa/nova_transferencia.html',
        empresas=empresas,
        tipos_servico=tipos_servico
    )


@bp_externa.route('/historico')
def historico_transferencia_externa():
    transferencias = TransferenciaExterna.query.order_by(TransferenciaExterna.data_hora.desc()).all()
    empresas = Empresa.query.order_by(Empresa.razao_social).all()
    return render_template(
        'transferencias/externa/historico_transferencias.html',
        transferencias=transferencias,
        empresas=empresas
    )


@bp_externa.route('/empresa/<int:id>')
def obter_dados_empresa(id):
    empresa = Empresa.query.get_or_404(id)
    return jsonify({
        'cnpj': empresa.cnpj,
        'endereco': empresa.endereco,
        'contato': empresa.contato
    })


@bp_externa.route('/detalhes/<int:id>')
def detalhes_transferencia_externa(id):
    transferencia = TransferenciaExterna.query.get_or_404(id)
    itens = transferencia.itens
    return render_template(
        'transferencias/externa/detalhes_transferencia.html',
        transferencia=transferencia,
        itens=itens
    )


@bp_externa.route('/registrar', methods=['POST'])
def registrar_transferencia_externa():
    data = request.form
    empresa_id = int(data.get('empresa_id'))
    autorizado_por = data.get('autorizado_por')
    retirado_por = data.get('retirado_por')
    tipo_servico_id = data.get('tipo_servico_id')

    if not tipo_servico_id:
        flash('Tipo de serviço inválido.', 'danger')
        return redirect(url_for('transferencia_externa.nova_transferencia_externa'))

    codigos = data.getlist('codigo[]')
    quantidades = data.getlist('quantidade[]')
    valores = data.getlist('valor_unitario[]')

    transferencia = TransferenciaExterna(
        empresa_id=empresa_id,
        autorizado_por=autorizado_por,
        retirado_por=retirado_por,
        tipo_servico_id=tipo_servico_id,
        data_hora=datetime.utcnow()
    )
    db.session.add(transferencia)
    db.session.flush()

    sucesso = False

    for i in range(len(codigos)):
        if not codigos[i] or not quantidades[i]:
            continue

        # Busca o item apenas pelo código
        item = Item.query.filter_by(codigo=codigos[i]).first()
        if not item:
            flash(f"Item {codigos[i]} não encontrado no cadastro!", "danger")
            continue

        # Busca o saldo do estoque para o tipo de serviço
        estoque = Estoque.query.filter_by(item_id=item.id, tipo_servico_id=tipo_servico_id).first()
        if not estoque:
            flash(f"Item {codigos[i]} não possui saldo para este tipo de serviço!", "danger")
            continue

        quantidade_transferida = int(quantidades[i])

        if estoque.quantidade < quantidade_transferida:
            flash(f"Saldo insuficiente para o item {codigos[i]}! Saldo disponível: {estoque.quantidade}", "danger")
            continue

        # Baixa do estoque central
        estoque.quantidade -= quantidade_transferida

        db.session.add(TransferenciaExternaItem(
            transferencia_id=transferencia.id,
            item_id=item.id,
            quantidade=quantidade_transferida,
            valor_unitario=float(valores[i]) if valores[i] else 0
        ))

        sucesso = True

    if not sucesso:
        db.session.rollback()
        flash("Nenhum item transferido. Corrija as quantidades e tente novamente.", "danger")
        return redirect(url_for('transferencia_externa.nova_transferencia_externa'))

    db.session.commit()
    flash('Transferência registrada com sucesso!', 'success')
    return redirect(url_for('transferencia_externa.historico_transferencia_externa'))


# --- API corrigida para trazer itens disponíveis corretamente
@bp_externa.route('/api/itens_disponiveis')
def api_itens_disponiveis():
    tipo_servico_id = request.args.get('tipo_servico_id')
    if not tipo_servico_id:
        return jsonify([])

    itens = (
        db.session.query(Item, Estoque)
        .join(Estoque, Item.id == Estoque.item_id)
        .filter(Estoque.tipo_servico_id == tipo_servico_id, Estoque.quantidade > 0)
        .order_by(Item.descricao)
        .all()
    )

    return jsonify([
        {
            'codigo': item.codigo,
            'descricao': item.descricao,
            'unidade': item.unidade,
            'valor': item.valor,
            'saldo': estoque.quantidade
        }
        for item, estoque in itens
    ])
