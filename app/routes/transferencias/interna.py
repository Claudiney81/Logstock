from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from app.extensions import db

from app.models import (
    MovimentacaoEstoque,
    MovimentacaoEstoqueItem,
    Tecnico,
    Empresa,
    TipoServico,
    Item,
    Estoque,
    SaldoTecnico
)

bp_movimentacao = Blueprint(
    'movimentacao_estoque',
    __name__,
    url_prefix='/movimentacao_estoque'
)


# ==========================================================
# NOVA MOVIMENTAÇÃO
# ==========================================================
@bp_movimentacao.route('/nova', methods=['GET', 'POST'])
@login_required
def nova_movimentacao():

    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    empresas = Empresa.query.order_by(Empresa.nome).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    if request.method == 'POST':

        origem_tipo = request.form.get('origem_tipo')
        origem_id = request.form.get('origem_id')

        destino_tipo = request.form.get('destino_tipo')
        destino_id = request.form.get('destino_id')

        tipo_servico_id = request.form.get('tipo_servico_id')
        observacao = request.form.get('observacao')

        codigos = request.form.getlist('codigo[]')
        quantidades = request.form.getlist('quantidade[]')
        valores = request.form.getlist('valor_unitario[]')

        if not origem_tipo or not origem_id:
            flash('Informe a origem.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        if not destino_tipo or not destino_id:
            flash('Informe o destino.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        if not tipo_servico_id:
            flash('Selecione o tipo de serviço.', 'danger')
            return redirect(url_for('movimentacao_estoque.nova_movimentacao'))

        nova_mov = MovimentacaoEstoque(
            origem_tipo=origem_tipo,
            origem_id=origem_id,
            destino_tipo=destino_tipo,
            destino_id=destino_id,
            tipo_servico_id=tipo_servico_id,
            observacao=observacao,
            usuario_id=current_user.id,
            data_hora=datetime.utcnow()
        )

        db.session.add(nova_mov)
        db.session.flush()

        sucesso = False

        # ==========================================================
        # LOOP DOS ITENS
        # ==========================================================
        for i in range(len(codigos)):

            if not codigos[i]:
                continue

            try:
                quantidade = int(quantidades[i])
            except:
                continue

            if quantidade <= 0:
                continue

            item = Item.query.filter_by(codigo=codigos[i]).first()

            if not item:
                flash(f'Item {codigos[i]} não encontrado.', 'danger')
                continue

            # ==========================================================
            # ORIGEM EMPRESA
            # ==========================================================
            if origem_tipo == 'empresa':

                estoque = Estoque.query.filter_by(
                    item_id=item.id,
                    tipo_servico_id=tipo_servico_id
                ).first()

                if not estoque:
                    flash(
                        f'Item {item.codigo} sem saldo no estoque.',
                        'danger'
                    )
                    continue

                if estoque.quantidade < quantidade:
                    flash(
                        f'Saldo insuficiente para {item.codigo}.',
                        'danger'
                    )
                    continue

                estoque.quantidade -= quantidade

            # ==========================================================
            # ORIGEM TÉCNICO
            # ==========================================================
            elif origem_tipo == 'tecnico':

                saldo = SaldoTecnico.query.filter_by(
                    tecnico_id=origem_id,
                    item_id=item.id,
                    tipo_servico_id=tipo_servico_id
                ).first()

                if not saldo:
                    flash(
                        f'Técnico sem saldo do item {item.codigo}.',
                        'danger'
                    )
                    continue

                if saldo.quantidade < quantidade:
                    flash(
                        f'Saldo insuficiente do técnico.',
                        'danger'
                    )
                    continue

                saldo.quantidade -= quantidade

            # ==========================================================
            # ITEM MOVIMENTAÇÃO
            # ==========================================================
            try:
                valor_unitario = float(valores[i]) if valores[i] else 0
            except:
                valor_unitario = 0

            item_mov = MovimentacaoEstoqueItem(
                movimentacao_id=nova_mov.id,
                item_id=item.id,
                quantidade=quantidade,
                valor_unitario=valor_unitario
            )

            db.session.add(item_mov)

            # ==========================================================
            # DESTINO TÉCNICO
            # ==========================================================
            if destino_tipo == 'tecnico':

                saldo_destino = SaldoTecnico.query.filter_by(
                    tecnico_id=destino_id,
                    item_id=item.id,
                    tipo_servico_id=tipo_servico_id
                ).first()

                if saldo_destino:

                    saldo_destino.quantidade += quantidade

                else:

                    novo_saldo = SaldoTecnico(
                        tecnico_id=destino_id,
                        item_id=item.id,
                        tipo_servico_id=tipo_servico_id,
                        quantidade=quantidade,
                        endereco='',
                        bairro='',
                        codigo_imovel='',
                        tipo_estoque=origem_tipo,
                        cliente_id=origem_id if origem_tipo == 'cliente' else None
                    )

                    db.session.add(novo_saldo)

            sucesso = True

        # ==========================================================
        # FINALIZA
        # ==========================================================
        if not sucesso:

            db.session.rollback()

            flash(
                'Nenhum item movimentado.',
                'danger'
            )

            return redirect(
                url_for('movimentacao_estoque.nova_movimentacao')
            )

        db.session.commit()

        flash(
            'Movimentação realizada com sucesso!',
            'success'
        )

        return redirect(
            url_for('movimentacao_estoque.historico')
        )

    return render_template(
        'movimentacao_estoque/nova.html',
        tecnicos=tecnicos,
        empresas=empresas,
        tipos_servico=tipos_servico
    )


# ==========================================================
# HISTÓRICO
# ==========================================================
@bp_movimentacao.route('/historico')
@login_required
def historico():

    movimentacoes = MovimentacaoEstoque.query.order_by(
        MovimentacaoEstoque.data_hora.desc()
    ).all()

    return render_template(
        'movimentacao_estoque/historico.html',
        movimentacoes=movimentacoes
    )


# ==========================================================
# DETALHES
# ==========================================================
@bp_movimentacao.route('/detalhes/<int:id>')
@login_required
def detalhes(id):

    movimentacao = MovimentacaoEstoque.query.get_or_404(id)

    return render_template(
        'movimentacao_estoque/detalhes.html',
        movimentacao=movimentacao
    )


# ==========================================================
# API ITENS DISPONÍVEIS
# ==========================================================
@bp_movimentacao.route('/api/itens')
@login_required
def api_itens():

    tipo_servico_id = request.args.get('tipo_servico_id')
    origem_tipo = request.args.get('origem_tipo')
    origem_id = request.args.get('origem_id')

    if not tipo_servico_id:
        return jsonify([])

    resultado = []

    # ==========================================================
    # EMPRESA
    # ==========================================================
    if origem_tipo == 'empresa':

        itens = (
            db.session.query(Item, Estoque)
            .join(Estoque, Item.id == Estoque.item_id)
            .filter(
                Estoque.tipo_servico_id == tipo_servico_id,
                Estoque.quantidade > 0
            )
            .all()
        )

        for item, estoque in itens:

            resultado.append({
                'codigo': item.codigo,
                'descricao': item.descricao,
                'unidade': item.unidade,
                'valor': item.valor,
                'saldo': estoque.quantidade
            })

    # ==========================================================
    # TÉCNICO
    # ==========================================================
    elif origem_tipo == 'tecnico':

        itens = (
            db.session.query(Item, SaldoTecnico)
            .join(SaldoTecnico, Item.id == SaldoTecnico.item_id)
            .filter(
                SaldoTecnico.tecnico_id == origem_id,
                SaldoTecnico.tipo_servico_id == tipo_servico_id,
                SaldoTecnico.quantidade > 0
            )
            .all()
        )

        for item, saldo in itens:

            resultado.append({
                'codigo': item.codigo,
                'descricao': item.descricao,
                'unidade': item.unidade,
                'valor': item.valor,
                'saldo': saldo.quantidade
            })

    return jsonify(resultado)