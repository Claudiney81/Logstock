from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Estoque, Item, TipoServico, InventarioEstoque, InventarioEstoqueItem
from flask_login import login_required, current_user

bp = Blueprint('inventario_estoque', __name__, url_prefix='/inventario_estoque')

# ===================== Inventário Principal =====================
@bp.route('/', methods=['GET'])
@login_required
def inventario():
    tipo_servico_filtro = request.args.get('tipo_servico')

    query = db.session.query(Estoque, Item, TipoServico) \
        .join(Item, Estoque.item_id == Item.id) \
        .outerjoin(TipoServico, Estoque.tipo_servico_id == TipoServico.id)

    # Aplica filtro apenas se houver um tipo de serviço selecionado
    if tipo_servico_filtro and tipo_servico_filtro.isdigit():
        query = query.filter(TipoServico.id == int(tipo_servico_filtro))

    resultados = query.all()
    tipos_servico = TipoServico.query.all()

    return render_template(
        'estoque/inventario.html',
        resultados=resultados,
        tipos_servico=tipos_servico,
        tipo_servico_filtro=tipo_servico_filtro
    )

# ===================== Finalizar Inventário =====================
@bp.route('/finalizar', methods=['POST'])
@login_required
def finalizar_inventario():
    inventario = InventarioEstoque(
        data_hora=datetime.now(),
        responsavel=current_user.nome
    )
    db.session.add(inventario)
    db.session.flush()

    alterou_algo = False

    for key, value in request.form.items():
        if key.startswith('contada_') and value.strip() != "":
            try:
                quantidade_contada = int(value)
            except ValueError:
                continue

            estoque_id = key.replace('contada_', '')
            estoque = Estoque.query.get(int(estoque_id))

            if estoque:
                alterou_algo = True
                quantidade_antes = estoque.quantidade  # saldo anterior

                # atualiza saldo do estoque
                estoque.quantidade = quantidade_contada

                # registra no histórico
                item_inventariado = InventarioEstoqueItem(
                    inventario_id=inventario.id,
                    item_id=estoque.item_id,
                    quantidade_estoque=quantidade_antes,
                    quantidade_contada=quantidade_contada
                )
                db.session.add(item_inventariado)

    if alterou_algo:
        db.session.commit()
        flash('Inventário finalizado com sucesso! Saldos atualizados.', 'success')
    else:
        db.session.rollback()
        flash('Nenhum item foi contado. Nenhuma alteração realizada.', 'warning')

    return redirect(url_for('inventario_estoque.inventario'))

# ===================== Histórico =====================
@bp.route('/historico')
@login_required
def historico_inventarios():
    responsavel = request.args.get('responsavel', '').strip()
    data_filtro = request.args.get('data', '').strip()
    page = request.args.get('page', 1, type=int)

    query = InventarioEstoque.query
    if responsavel:
        query = query.filter(InventarioEstoque.responsavel.ilike(f"%{responsavel}%"))
    if data_filtro:
        query = query.filter(db.func.date(InventarioEstoque.data_hora) == data_filtro)

    inventarios = query.order_by(InventarioEstoque.data_hora.desc()).paginate(page=page, per_page=10)

    return render_template('estoque/inventario_historico.html',
                           inventarios=inventarios,
                           responsavel=responsavel,
                           data_filtro=data_filtro)

# ===================== Detalhes de um inventário =====================
@bp.route('/historico/<int:inventario_id>')
@login_required
def historico_inventario_detalhe(inventario_id):
    inventario = InventarioEstoque.query.get_or_404(inventario_id)
    itens = (
        db.session.query(Item.id, Item.codigo, Item.descricao, Item.unidade,
                         InventarioEstoqueItem.quantidade_contada)
        .join(Item, InventarioEstoqueItem.item_id == Item.id)
        .filter(InventarioEstoqueItem.inventario_id == inventario.id)
        .all()
    )
    return render_template('estoque/inventario_historico_detalhe.html',
                           inventario=inventario,
                           itens=itens)
