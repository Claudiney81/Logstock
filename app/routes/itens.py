from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models import Item, Estoque, NotaFiscalItem, RequisicaoTecnicoItem, db

bp = Blueprint('itens', __name__, url_prefix='/itens')

@bp.route('/buscar_item', methods=['GET'])
def buscar_item():
    codigo = request.args.get('codigo', '').strip().upper()
    item = Item.query.filter_by(codigo=codigo).first()
    if not item:
        return jsonify({'erro': 'Item não encontrado'}), 404

    estoque = Estoque.query.filter_by(item_id=item.id).first()
    quantidade = estoque.quantidade if estoque else 0

    if quantidade <= 0:
        return jsonify({'erro': 'Sem saldo em estoque!'}), 404

    return jsonify({
        'descricao': item.descricao,
        'unidade': item.unidade,
        'valor': item.valor,
        'quantidade': quantidade
    })


# ---- EDIÇÃO DE ITEM ----
@bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    item = Item.query.get_or_404(id)
    if request.method == 'POST':
        item.descricao = request.form['descricao']
        item.unidade = request.form['unidade']
        item.valor = request.form['valor']
        # Novo campo para indicar se é ferramenta/equipamento
        item.eh_equipamento = True if request.form.get('eh_equipamento') else False
        db.session.commit()
        flash('Item editado com sucesso!', 'success')
        return redirect(url_for('estoque.listar_itens'))
    return render_template('itens/editar.html', item=item)


# ---- EXCLUSÃO COMPLETA DE ITEM ----
@bp.route('/excluir/<int:id>', methods=['POST', 'GET'])
def excluir(id):
    item = Item.query.get_or_404(id)

    # Remove relacionamentos antes de excluir o item
    Estoque.query.filter_by(item_id=item.id).delete()
    NotaFiscalItem.query.filter_by(item_id=item.id).delete()
    RequisicaoTecnicoItem.query.filter_by(codigo=item.codigo).delete()

    db.session.delete(item)
    db.session.commit()
    flash('Item e registros relacionados excluídos com sucesso!', 'success')
    return redirect(url_for('estoque.listar_itens'))
