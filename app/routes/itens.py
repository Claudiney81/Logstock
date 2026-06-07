from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models import Item, Estoque, NotaFiscalItem, RequisicaoTecnicoItem, db

bp = Blueprint('itens', __name__, url_prefix='/itens')


def converter_valor(valor):
    if valor is None:
        return 0.0

    valor = str(valor).strip()
    valor = valor.replace("R$", "").replace(" ", "")

    if not valor:
        return 0.0

    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except Exception:
        return 0.0


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
        'quantidade': quantidade,
        'categoria': item.categoria or 'MATERIAL'
    })


# ---- EDIÇÃO DE ITEM ----
@bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    item = Item.query.get_or_404(id)

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().upper()
        descricao = request.form.get('descricao', '').strip()
        unidade = request.form.get('unidade', '').strip()

        if not codigo:
            flash('Código do item é obrigatório.', 'warning')
            return redirect(url_for('itens.editar', id=item.id))

        item_com_mesmo_codigo = Item.query.filter(
            Item.codigo == codigo,
            Item.id != item.id
        ).first()

        if item_com_mesmo_codigo:
            flash('Já existe outro item com este código.', 'warning')
            return redirect(url_for('itens.editar', id=item.id))

        item.codigo = codigo
        item.descricao = descricao
        item.unidade = unidade
        item.valor = converter_valor(request.form.get('valor', '0'))

        categoria = request.form.get(
            'categoria',
            item.categoria or 'MATERIAL'
        ).strip().upper()

        if categoria not in ['MATERIAL', 'FERRAMENTA', 'EPI']:
            categoria = item.categoria or 'MATERIAL'

        item.categoria = categoria
        item.eh_equipamento = categoria in ['FERRAMENTA', 'EPI']

        db.session.commit()

        return redirect(url_for('estoque.listar_itens'))

    return render_template('itens/editar.html', item=item)


# ---- EXCLUSÃO COMPLETA DE ITEM ----
@bp.route('/excluir/<int:id>', methods=['POST', 'GET'])
def excluir(id):
    item = Item.query.get_or_404(id)

    Estoque.query.filter_by(item_id=item.id).delete()
    NotaFiscalItem.query.filter_by(item_id=item.id).delete()
    RequisicaoTecnicoItem.query.filter_by(codigo=item.codigo).delete()

    db.session.delete(item)
    db.session.commit()

    flash('Item e registros relacionados excluídos com sucesso!', 'success')
    return redirect(url_for('estoque.listar_itens'))