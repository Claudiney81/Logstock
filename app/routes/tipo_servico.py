from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import TipoServico


tipo_servico_bp = Blueprint('tipo_servico', __name__)


PERFIS_GESTAO = {"admin", "estoque"}


def _pode_gerenciar():
    return getattr(current_user, "perfil", None) in PERFIS_GESTAO


def _referencias_do_tipo(tipo):
    """Retorna vínculos que impedem a exclusão do cadastro."""
    referencias = []
    tabela_tipo = TipoServico.__table__.fullname

    for tabela in db.metadata.sorted_tables:
        for coluna in tabela.columns:
            if not any(fk.target_fullname == f"{tabela_tipo}.id" for fk in coluna.foreign_keys):
                continue

            quantidade = db.session.execute(
                db.select(func.count()).select_from(tabela).where(coluna == tipo.id)
            ).scalar_one()
            if quantidade:
                referencias.append((tabela.name, quantidade))

    # Há registros antigos que guardam o nome, e não o ID, do tipo de serviço.
    for nome_tabela in ("requisicoes_tecnicos", "notas_fiscais_entrada"):
        tabela = db.metadata.tables.get(nome_tabela)
        if tabela is None or "tipo_servico" not in tabela.c:
            continue
        quantidade = db.session.execute(
            db.select(func.count()).select_from(tabela).where(
                func.lower(func.trim(tabela.c.tipo_servico)) == tipo.nome.strip().lower()
            )
        ).scalar_one()
        if quantidade:
            referencias.append((f"{nome_tabela} (histórico)", quantidade))

    return referencias


def _atualizar_nome_historico(nome_antigo, nome_novo):
    """Mantém compatibilidade com registros antigos que armazenam apenas o nome."""
    for nome_tabela in ("requisicoes_tecnicos", "notas_fiscais_entrada"):
        tabela = db.metadata.tables.get(nome_tabela)
        if tabela is None or "tipo_servico" not in tabela.c:
            continue
        db.session.execute(
            tabela.update().where(
                func.lower(func.trim(tabela.c.tipo_servico)) == nome_antigo.strip().lower()
            ).values(tipo_servico=nome_novo)
        )


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
        tipos=tipos,
        pode_gerenciar=_pode_gerenciar()
    )


@tipo_servico_bp.route('/cadastro/tipo-servico/<int:tipo_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_tipo_servico(tipo_id):
    if not _pode_gerenciar():
        flash("Acesso permitido apenas para administrador ou estoque.", "danger")
        return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))

    tipo = TipoServico.query.get_or_404(tipo_id)

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        tipo_estoque = (request.form.get('tipo_estoque') or '').strip()

        if not nome or tipo_estoque not in ["empresa", "cliente"]:
            flash("Informe um nome e um tipo de estoque válidos.", "warning")
            return render_template("cadastros/editar_tipo_servico.html", tipo=tipo)

        duplicado = TipoServico.query.filter(
            TipoServico.id != tipo.id,
            func.lower(TipoServico.nome) == nome.lower(),
            TipoServico.tipo_estoque == tipo_estoque
        ).first()
        if duplicado:
            flash("Já existe esse tipo de serviço para o estoque selecionado.", "danger")
            return render_template("cadastros/editar_tipo_servico.html", tipo=tipo)

        if tipo_estoque != tipo.tipo_estoque and _referencias_do_tipo(tipo):
            flash("O tipo de estoque não pode ser alterado porque este cadastro já está em uso.", "danger")
            return render_template("cadastros/editar_tipo_servico.html", tipo=tipo)

        nome_antigo = tipo.nome
        if nome != nome_antigo:
            _atualizar_nome_historico(nome_antigo, nome)
        tipo.nome = nome
        tipo.tipo_estoque = tipo_estoque
        db.session.commit()
        flash("Tipo de serviço atualizado com sucesso!", "success")
        return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))

    return render_template("cadastros/editar_tipo_servico.html", tipo=tipo)


@tipo_servico_bp.route('/cadastro/tipo-servico/<int:tipo_id>/excluir', methods=['POST'])
@login_required
def excluir_tipo_servico(tipo_id):
    if not _pode_gerenciar():
        flash("Acesso permitido apenas para administrador ou estoque.", "danger")
        return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))

    tipo = TipoServico.query.get_or_404(tipo_id)
    referencias = _referencias_do_tipo(tipo)
    if referencias:
        total = sum(quantidade for _, quantidade in referencias)
        flash(
            f'Não foi possível excluir "{tipo.nome}": existem {total} registro(s) vinculado(s).',
            "danger"
        )
        return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))

    nome = tipo.nome
    db.session.delete(tipo)
    db.session.commit()
    flash(f'Tipo de serviço "{nome}" excluído com sucesso!', "success")
    return redirect(url_for("tipo_servico.cadastrar_tipo_servico"))
