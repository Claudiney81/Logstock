from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.extensions import db
from app.models import TipoServico


tipo_servico_bp = Blueprint('tipo_servico', __name__)


# ==================================================
# Cadastro e listagem de Tipo de Serviço
# Regra:
# - Pode cadastrar novo tipo
# - Não edita
# - Não exclui
# ==================================================
@tipo_servico_bp.route('/cadastro/tipo-servico', methods=['GET', 'POST'])
@login_required
def cadastrar_tipo_servico():

    if request.method == 'POST':

        nome = (request.form.get('nome') or '').strip()
        tipo_estoque = (request.form.get('tipo_estoque') or '').strip()

        if not nome:
            flash("O nome do tipo de serviço é obrigatório.", "warning")
            return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))

        if tipo_estoque not in ["empresa", "cliente"]:
            flash("Selecione o tipo de estoque: Empresa ou Cliente.", "warning")
            return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))

        existente = TipoServico.query.filter_by(
            nome=nome,
            tipo_estoque=tipo_estoque
        ).first()

        if existente:
            flash(
                "Este tipo de serviço já está cadastrado para este tipo de estoque.",
                "danger"
            )
            return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))

        novo_tipo = TipoServico(
            nome=nome,
            tipo_estoque=tipo_estoque
        )

        db.session.add(novo_tipo)
        db.session.commit()

        flash("Tipo de serviço cadastrado com sucesso!", "success")
        return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))

    tipos = (
        TipoServico.query
        .order_by(
            TipoServico.nome.asc(),
            TipoServico.tipo_estoque.asc()
        )
        .all()
    )

    return render_template(
        "cadastros/tipo_servico.html",
        tipos=tipos
    )