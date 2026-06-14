# app/routes/requisicao_mobile.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime

from app.extensions import db
from app.models import (
    Usuario,
    Tecnico,
    TipoServico,
    Empresa,
    Item,
    Estoque,
    RequisicaoTecnico,
    RequisicaoTecnicoItem
)

bp_requisicao_mobile = Blueprint(
    "requisicao_mobile",
    __name__
)


@bp_requisicao_mobile.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "").strip()

        usuario = Usuario.query.filter(
            Usuario.email == email,
            Usuario.perfil.in_(["tecnico", "admin"])
        ).first()

        if usuario and check_password_hash(usuario.senha_hash, senha):

            login_user(usuario)

            tecnico = None

            if hasattr(usuario, "tecnico") and usuario.tecnico:
                tecnico = usuario.tecnico

            if not tecnico:
                tecnico = Tecnico.query.filter_by(email=email).first()

            if not tecnico:
                flash("Usuário autenticado, mas não existe técnico vinculado a este email.", "danger")
                return redirect(url_for("requisicao_mobile.login"))

            session["tecnico_id"] = tecnico.id
            session["tecnico_nome"] = tecnico.nome
            session["perfil"] = "tecnico_requisicao_mobile"

            return redirect(url_for("requisicao_mobile.nova"))

        flash("Email ou senha inválidos.", "danger")

    return render_template("requisicao_mobile/login.html")


@bp_requisicao_mobile.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("requisicao_mobile.login"))


def get_tecnico_mobile_logado():
    tecnico_id = session.get("tecnico_id")

    if tecnico_id:
        tecnico = Tecnico.query.get(tecnico_id)
        if tecnico:
            return tecnico

    if current_user.is_authenticated and getattr(current_user, "tecnico_id", None):
        return Tecnico.query.get(current_user.tecnico_id)

    return None


def montar_nome_cliente_os(cliente):
    if not cliente:
        return None

    numero_os = (
        getattr(cliente, "numero_os", None)
        or getattr(cliente, "codigo_os", None)
        or getattr(cliente, "os", None)
    )

    if numero_os:
        return f"{cliente.razao_social} - {numero_os}"

    return cliente.razao_social


def item_eh_material(item):
    """
    Requisição Mobile deve permitir somente MATERIAL.
    Bloqueia Ferramenta, EPI e qualquer item marcado como equipamento.
    """

    if not item:
        return False

    categoria = (item.categoria or "").strip().lower()

    eh_equipamento = bool(getattr(item, "eh_equipamento", False))

    if eh_equipamento:
        return False

    if categoria in ["ferramenta", "ferramentas", "epi", "epis", "equipamento", "equipamentos"]:
        return False

    return categoria in ["", "material"]


@bp_requisicao_mobile.route("/nova", methods=["GET", "POST"])
@login_required
def nova():

    tecnico = get_tecnico_mobile_logado()

    if not tecnico:
        flash("Técnico não localizado para este login.", "danger")
        return redirect(url_for("requisicao_mobile.login"))

    if request.method == "POST":

        # FORMULÁRIO MOBILE SIMPLIFICADO:
        # Técnico solicita apenas MATERIAL do estoque EMPRESA.
        tipo_estoque = "empresa"
        tipo_servico_id = request.form.get("tipo_servico_id", type=int)
        observacao = request.form.get("observacao", "").strip() or "N/D"

        cliente_id = None
        endereco = ""
        os_cliente = None

        item_ids = request.form.getlist("item_id[]")
        quantidades = request.form.getlist("quantidade[]")        
      
        tipo_servico = TipoServico.query.get(tipo_servico_id)

        if not tipo_servico:
            flash("Selecione o tipo de serviço.", "warning")
            return redirect(url_for("requisicao_mobile.nova"))

        if not item_ids:
            flash("Adicione pelo menos um item.", "warning")
            return redirect(url_for("requisicao_mobile.nova"))

        try:

            requisicao = RequisicaoTecnico(
                solicitante_responsavel=tecnico.nome,
                solicitante_tecnico=tecnico.nome,
                solicitante_tecnico_id=tecnico.id,

                tipo_estoque=tipo_estoque,

                cliente_id=cliente_id,
                os_cliente=os_cliente,

                tipo_servico=tipo_servico.nome,

                endereco=endereco,
                observacao=observacao,

                origem_mobile=True,
                status="pendente",

                data_hora=datetime.now()
            )

            db.session.add(requisicao)
            db.session.flush()

            total_itens = 0

            for item_id, qtd in zip(item_ids, quantidades):

                if not item_id or not qtd:
                    continue

                try:
                    item_id = int(item_id)
                    quantidade = int(qtd)
                except ValueError:
                    continue

                if quantidade <= 0:
                    continue

                item = Item.query.get(item_id)

                if not item:
                    continue

                if not item_eh_material(item):
                    db.session.rollback()
                    flash(
                        f"O item {item.codigo} - {item.descricao} não é material "
                        f"e não pode ser solicitado nesta requisição.",
                        "warning"
                    )
                    return redirect(url_for("requisicao_mobile.nova"))

                estoque_query = Estoque.query.filter(
                    Estoque.item_id == item.id,
                    Estoque.tipo_servico_id == 1,
                    Estoque.tipo_estoque == tipo_estoque,
                    Estoque.cliente_id.is_(None)
                )

                estoques_item = estoque_query.all()
                quantidade_estoque = sum(e.quantidade or 0 for e in estoques_item)
                valor_estoque = next(
                    (
                        float(e.valor_unitario)
                        for e in estoques_item
                        if e.valor_unitario is not None
                    ),
                    float(item.valor or 0)
                )

                if quantidade_estoque <= 0:
                    db.session.rollback()
                    flash(
                        f"O item {item.codigo} - {item.descricao} está sem saldo disponível.",
                        "warning"
                    )
                    return redirect(url_for("requisicao_mobile.nova"))

                if quantidade > quantidade_estoque:
                    db.session.rollback()
                    flash(
                        f"Quantidade solicitada do item {item.codigo} é maior que o saldo disponível. "
                        f"Saldo atual: {quantidade_estoque}.",
                        "warning"
                    )
                    return redirect(url_for("requisicao_mobile.nova"))

                novo_item = RequisicaoTecnicoItem(
                    requisicao_id=requisicao.id,
                    codigo=item.codigo,
                    descricao=item.descricao,
                    unidade=item.unidade,
                    quantidade=quantidade,
                    valor=valor_estoque,
                    quantidade_estoque=quantidade_estoque
                )

                db.session.add(novo_item)
                total_itens += 1

            if total_itens == 0:
                db.session.rollback()
                flash("Adicione pelo menos um item válido.", "warning")
                return redirect(url_for("requisicao_mobile.nova"))

            db.session.commit()

            return redirect(
                url_for(
                    "tecnico_mobile.home",
                    sucesso="requisicao_enviada"
                )
            )

        except Exception as e:
            db.session.rollback()
            print("ERRO REQUISIÇÃO MOBILE:", e)
            flash("Erro ao enviar requisição mobile.", "danger")
            return redirect(url_for("requisicao_mobile.nova"))

    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    clientes = (
        Empresa.query
        .filter(Empresa.razao_social != "CCM LOGISTICA LTDA")
        .order_by(Empresa.razao_social)
        .all()
    )

    return render_template(
        "requisicao_mobile/nova.html",
        tecnico=tecnico,
        tipos_servico=tipos_servico,
        clientes=clientes
    )


@bp_requisicao_mobile.route("/api/itens/<int:tipo_servico_id>")
@login_required
def api_itens_empresa_padrao(tipo_servico_id):
    return buscar_itens_por_estoque(tipo_servico_id, "empresa")


@bp_requisicao_mobile.route("/api/itens/<int:tipo_servico_id>/<tipo_estoque>")
@login_required
def api_itens_por_estoque(tipo_servico_id, tipo_estoque):

    if tipo_estoque not in ["empresa", "cliente"]:
        return {"itens": []}

    return buscar_itens_por_estoque(tipo_servico_id, tipo_estoque)


def buscar_itens_por_estoque(tipo_servico_id, tipo_estoque):

    # REGRA LOGISTOCK:
    # Estoque Empresa/Cliente possui saldo físico somente em Instalação.
    # Manutenção e Reparo usam o saldo de Instalação.
    tipo_servico_saldo_id = 1

    valor_estoque = db.func.coalesce(
        db.func.max(Estoque.valor_unitario),
        Item.valor
    ).label("valor")

    query = (
        db.session.query(
            Item.id.label("id"),
            Item.codigo.label("codigo"),
            Item.descricao.label("descricao"),
            Item.unidade.label("unidade"),
            valor_estoque,
            Item.categoria.label("categoria"),
            Item.eh_equipamento.label("eh_equipamento"),
            db.func.sum(Estoque.quantidade).label("saldo")
        )
        .join(Estoque, Estoque.item_id == Item.id)
        .filter(
            Estoque.tipo_servico_id == tipo_servico_saldo_id,
            Estoque.tipo_estoque == tipo_estoque,
            Estoque.quantidade > 0,

            # REQUISIÇÃO MOBILE: somente MATERIAL
            db.or_(
                Item.categoria == None,
                Item.categoria == "",
                db.func.lower(Item.categoria) == "material"
            ),
            db.or_(
                Item.eh_equipamento == False,
                Item.eh_equipamento == None
            )
        )
    )

    if tipo_estoque == "empresa" and hasattr(Estoque, "cliente_id"):
        query = query.filter(Estoque.cliente_id.is_(None))

    itens = (
        query
        .group_by(
            Item.id,
            Item.codigo,
            Item.descricao,
            Item.unidade,
            Item.valor,
            Item.categoria,
            Item.eh_equipamento
        )
        .order_by(Item.descricao.asc())
        .all()
    )

    resultado = []

    for item in itens:

        if not item_eh_material(item):
            continue

        resultado.append({
            "id": item.id,
            "codigo": item.codigo,
            "descricao": item.descricao,
            "unidade": item.unidade,
            "valor": item.valor or 0,
            "saldo": int(item.saldo or 0)
        })

    return {"itens": resultado}
