from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session
)

from flask_login import (
    login_required,
    current_user,
    login_user,
    logout_user
)

from datetime import datetime
from sqlalchemy import func
import os

from werkzeug.utils import secure_filename
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from app import db

from app.models import (
    Tecnico,
    SaldoTecnico,
    BaixaTecnica,
    BaixaTecnicaItem,
    BaixaTecnicaFoto,
    TipoServico,
    Empresa,
    Item,
    Usuario,
    OrdemServico
)

bp_baixa_tecnico = Blueprint(
    "baixa_tecnico",
    __name__,
    url_prefix="/baixa_tecnico"
)


# ==========================================================
# LOCALIZAR TÉCNICO LOGADO
# ==========================================================

def get_tecnico_mobile():
    tecnico_id = session.get("tecnico_id")

    if tecnico_id:
        tecnico = Tecnico.query.get(tecnico_id)
        if tecnico:
            return tecnico

    if current_user.is_authenticated:
        if getattr(current_user, "tecnico_id", None):
            tecnico = Tecnico.query.get(current_user.tecnico_id)
            if tecnico:
                return tecnico

        if getattr(current_user, "email", None):
            tecnico = Tecnico.query.filter_by(email=current_user.email).first()
            if tecnico:
                return tecnico

    tecnico_id = request.args.get("tecnico_id", type=int)

    if tecnico_id:
        return Tecnico.query.get(tecnico_id)

    return None


# ==========================================================
# BAIXA - LINK ANTIGO / PORTAL
# ==========================================================

@bp_baixa_tecnico.route("/formulario", methods=["GET"])
@login_required
def formulario_baixa():
    tecnico = get_tecnico_mobile()

    if not tecnico:
        flash("Técnico não encontrado. Faça login novamente.", "warning")
        return redirect(url_for("auth.login"))

    return redirect(
        url_for(
            "baixa_tecnico.formulario_mobile_dedicado",
            tecnico_id=tecnico.id
        )
    )


# ==========================================================
# FORMULÁRIO MOBILE DEDICADO
# ==========================================================

@bp_baixa_tecnico.route("/mobile", methods=["GET"])
@bp_baixa_tecnico.route("/mobile/<int:tecnico_id>", methods=["GET"])
@login_required
def formulario_mobile_dedicado(tecnico_id=None):

    if tecnico_id:
        tecnico = Tecnico.query.get_or_404(tecnico_id)
    else:
        tecnico = get_tecnico_mobile()

    if not tecnico:
        flash("Técnico não encontrado.", "warning")
        return redirect(url_for("tecnico_mobile.login"))

    tipos_servico = (
        TipoServico.query
        .order_by(TipoServico.nome)
        .all()
    )

    clientes = (
    db.session.query(Empresa)
    .join(
        SaldoTecnico,
        SaldoTecnico.cliente_id == Empresa.id
    )
    .filter(
        SaldoTecnico.tecnico_id == tecnico.id
    )
    .filter(
        SaldoTecnico.cliente_id.isnot(None)
    )
    .filter(
        SaldoTecnico.quantidade > 0
    )
    .filter(
        Empresa.razao_social.notilike("%CCM%")
    )
    .filter(
        db.func.lower(Empresa.tipo_empresa) == "cliente"
    )
    .distinct()
    .order_by(
        Empresa.razao_social
    )
    .all()
)

    baixas_recusadas = (
        BaixaTecnica.query
        .filter(
            BaixaTecnica.tecnico_id == tecnico.id,
            BaixaTecnica.status.in_(["recusado", "pendente_ajuste"]),
            BaixaTecnica.origem_mobile == True
        )
        .order_by(BaixaTecnica.data_hora.desc())
        .all()
    )

    return render_template(
        "baixa_tecnico/formulario_mobile_dedicado.html",
        tecnico=tecnico,
        tecnico_id=tecnico.id,
        tecnico_nome=tecnico.nome,
        tipos_servico=tipos_servico,
        clientes=clientes,
        baixas_recusadas=baixas_recusadas
    )
    
# ==========================================================
# API O.S POR CLIENTE - BASEADA NO SALDO TÉCNICO
# ==========================================================

@bp_baixa_tecnico.route("/api/os-por-cliente")
@login_required
def api_os_por_cliente():
    tecnico_id = request.args.get("tecnico_id", type=int)
    cliente_id = request.args.get("cliente_id", type=int)

    if not tecnico_id or not cliente_id:
        return jsonify({"ordens": []})

    if not OrdemServico:
        return jsonify({"ordens": []})

    registros = (
        db.session.query(
            SaldoTecnico.ordem_servico_id,
            OrdemServico.numero_os,
            OrdemServico.endereco,
            SaldoTecnico.endereco.label("endereco_saldo"),
            SaldoTecnico.tipo_servico_id,
            TipoServico.nome.label("tipo_servico_nome")
        )
        .join(
            OrdemServico,
            OrdemServico.id == SaldoTecnico.ordem_servico_id
        )
        .join(
            TipoServico,
            TipoServico.id == SaldoTecnico.tipo_servico_id
        )
        .filter(
            SaldoTecnico.tecnico_id == tecnico_id,
            SaldoTecnico.cliente_id == cliente_id,
            SaldoTecnico.ordem_servico_id.isnot(None),
            SaldoTecnico.quantidade > 0
        )
        .group_by(
            SaldoTecnico.ordem_servico_id,
            OrdemServico.numero_os,
            OrdemServico.endereco,
            SaldoTecnico.endereco,
            SaldoTecnico.tipo_servico_id,
            TipoServico.nome
        )
        .order_by(
            OrdemServico.numero_os
        )
        .all()
    )

    ordens = []
    os_adicionadas = set()

    for r in registros:

        if r.ordem_servico_id in os_adicionadas:
            continue

        os_adicionadas.add(r.ordem_servico_id)

        ordens.append({
            "ordem_servico_id": r.ordem_servico_id,
            "numero_os": r.numero_os,
            "endereco": r.endereco or r.endereco_saldo or "",
            "tipo_servico_id": r.tipo_servico_id,
            "tipo_servico_nome": r.tipo_servico_nome or ""
        })

    return jsonify({"ordens": ordens})


# ==========================================================
# ALTERAR SENHA TÉCNICO
# ==========================================================

@bp_baixa_tecnico.route("/alterar-senha", methods=["GET", "POST"])
@login_required
def alterar_senha_tecnico():

    tecnico = get_tecnico_mobile()

    if not tecnico:
        flash("Técnico não encontrado. Faça login novamente.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        nova_senha = request.form.get("nova_senha", "").strip()
        confirmar_senha = request.form.get("confirmar_senha", "").strip()

        if not nova_senha or not confirmar_senha:
            flash("Preencha todos os campos.", "warning")
            return redirect(url_for("baixa_tecnico.alterar_senha_tecnico"))

        if nova_senha != confirmar_senha:
            flash("As senhas não conferem.", "danger")
            return redirect(url_for("baixa_tecnico.alterar_senha_tecnico"))

        if hasattr(current_user, "set_password"):
            current_user.set_password(nova_senha)
        elif hasattr(current_user, "senha_hash"):
            current_user.senha_hash = generate_password_hash(nova_senha)
        elif hasattr(current_user, "senha"):
            current_user.senha = generate_password_hash(nova_senha)

        db.session.commit()

        flash("Senha alterada com sucesso.", "success")
        return redirect(
            url_for(
                "baixa_tecnico.formulario_mobile_dedicado",
                tecnico_id=tecnico.id
            )
        )

    return render_template(
        "baixas_mobile/alterar_senha.html",
        tecnico=tecnico
    )

# Estoque Empresa: mostra tudo do técnico nesse tipo de serviço
# Estoque Empresa: filtra cliente + O.S
@bp_baixa_tecnico.route("/api/itens")
@login_required
def api_itens():
    tecnico_id = request.args.get("tecnico_id", type=int)
    tipo_servico_id = request.args.get("tipo_servico_id", type=int)
    tipo_estoque = (request.args.get("tipo_estoque") or "").strip().lower()
    cliente_id = request.args.get("cliente_id", type=int)
    ordem_servico_id = request.args.get("ordem_servico_id", type=int)

    if not tecnico_id or not tipo_servico_id:
        return jsonify({"itens": []})

    if tipo_estoque not in ["empresa", "cliente"]:
        return jsonify({"itens": []})

    if tipo_estoque == "cliente":
        if not cliente_id or not ordem_servico_id:
            return jsonify({"itens": []})

    query = db.session.query(
        SaldoTecnico.item_id,
        SaldoTecnico.tipo_estoque,
        func.sum(SaldoTecnico.quantidade).label("saldo")
    ).filter(
        SaldoTecnico.tecnico_id == tecnico_id,
        SaldoTecnico.tipo_servico_id == tipo_servico_id,
        SaldoTecnico.tipo_estoque == tipo_estoque,
        SaldoTecnico.quantidade > 0
    )

    if tipo_estoque == "cliente":
        query = query.filter(
            SaldoTecnico.cliente_id == cliente_id,
            SaldoTecnico.ordem_servico_id == ordem_servico_id
        )

    elif tipo_estoque == "empresa":
        query = query.filter(
            SaldoTecnico.cliente_id.is_(None),
            SaldoTecnico.ordem_servico_id.is_(None)
        )

    rows = (
        query
        .group_by(
            SaldoTecnico.item_id,
            SaldoTecnico.tipo_estoque
        )
        .all()
    )

    resultado = []

    for item_id, tipo_registro, saldo in rows:
        item = Item.query.get(item_id)

        if item and int(saldo or 0) > 0:
            resultado.append({
                "item_id": item.id,
                "codigo": item.codigo,
                "descricao": item.descricao,
                "unidade": item.unidade,
                "saldo": int(saldo or 0),
                "valor": float(item.valor or 0)
            })

    return jsonify({"itens": resultado})
# ==========================================================
# REGISTRAR BAIXA MOBILE
# ==========================================================

@bp_baixa_tecnico.route("/registrar", methods=["POST"])
@login_required
def registrar():
    tecnico_id = request.form.get("tecnico_id", type=int)
    tipo_servico_id = request.form.get("tipo_servico_id", type=int)
    cliente_id = request.form.get("cliente_id", type=int)
    ordem_servico_id = request.form.get("ordem_servico_id", type=int)

    endereco = request.form.get("endereco", "").strip()
    observacao = request.form.get("observacao", "").strip()
    ordem_servico = request.form.get("ordem_servico", "").strip()

    tecnico = Tecnico.query.get(tecnico_id)
    responsavel = tecnico.nome if tecnico else "Técnico"

    if not tecnico_id or not tipo_servico_id:
        flash("Preencha Tipo de Serviço.", "warning")
        return redirect(
            url_for(
                "baixa_tecnico.formulario_mobile_dedicado",
                tecnico_id=tecnico_id
            )
        )

    item_ids = request.form.getlist("item_id[]")
    quantidades = request.form.getlist("quantidade[]")
    tipos_estoque = request.form.getlist("tipo_estoque[]")
    clientes_estoque = request.form.getlist("cliente_estoque_id[]")

    if not item_ids:
        flash("Adicione ao menos um item à baixa.", "warning")
        return redirect(
            url_for(
                "baixa_tecnico.formulario_mobile_dedicado",
                tecnico_id=tecnico_id
            )
        )

    cliente = Empresa.query.get(cliente_id) if cliente_id else None

    itens_validos = []

    for item_id, qtd, tipo_est, cliente_est in zip(
        item_ids,
        quantidades,
        tipos_estoque,
        clientes_estoque
    ):
        try:
            item_id = int(item_id)
            qtd = int(qtd or 0)

            cliente_est = (
                int(cliente_est)
                if cliente_est and str(cliente_est).isdigit()
                else None
            )

        except Exception:
            continue

        tipo_est = (tipo_est or "empresa").strip().lower()

        if tipo_est not in ["empresa", "cliente"]:
            tipo_est = "empresa"

        if item_id and qtd > 0:
            itens_validos.append({
                "item_id": item_id,
                "quantidade": qtd,
                "tipo_estoque": tipo_est,
                "cliente_estoque_id": cliente_est if tipo_est == "cliente" else None
            })

    if not itens_validos:
        flash("Informe ao menos um item com quantidade.", "warning")
        return redirect(
            url_for(
                "baixa_tecnico.formulario_mobile_dedicado",
                tecnico_id=tecnico_id
            )
        )

    try:
        nome_cliente_os = None

        if cliente:
            nome_cliente_os = cliente.razao_social

            if getattr(cliente, "numero_os", None):
                nome_cliente_os += f" - {cliente.numero_os}"
            elif ordem_servico:
                nome_cliente_os += f" - {ordem_servico}"

        baixa_existente = (
            BaixaTecnica.query
            .filter(
                BaixaTecnica.tecnico_id == tecnico_id,
                BaixaTecnica.status.in_(["recusado", "pendente_ajuste"]),
                BaixaTecnica.visualizado_tecnico == False,
                BaixaTecnica.origem_mobile == True
            )
            .order_by(BaixaTecnica.data_hora.desc())
            .first()
        )

        if baixa_existente:
            baixa = baixa_existente

            baixa.tipo_servico_id = tipo_servico_id
            baixa.cliente_id = cliente_id
            baixa.ordem_servico_id = ordem_servico_id
            baixa.os_cliente = nome_cliente_os
            baixa.endereco = endereco
            baixa.observacao = observacao
            baixa.status = "pendente"
            baixa.motivo_recusa = None
            baixa.visualizado_tecnico = False

            for item_antigo in list(baixa.itens):
                if item_antigo.status in ["recusado", "pendente_ajuste"]:
                    db.session.delete(item_antigo)

            db.session.flush()

        else:
            baixa = BaixaTecnica(
                tecnico_id=tecnico_id,
                tipo_servico_id=tipo_servico_id,
                cliente_id=cliente_id,
                ordem_servico_id=ordem_servico_id,
                os_cliente=nome_cliente_os,
                endereco=endereco,
                responsavel=responsavel,
                observacao=observacao,
                status="pendente",
                origem_mobile=True,
                data_hora=datetime.now()
            )

            db.session.add(baixa)
            db.session.flush()

        fotos = request.files.getlist("fotos[]")
        legendas = request.form.getlist("legenda_foto[]")

        pasta_upload = os.path.join(
            "app",
            "static",
            "uploads",
            "baixas"
        )

        os.makedirs(pasta_upload, exist_ok=True)

        for i, foto in enumerate(fotos):

            if not foto or not foto.filename:
                continue

            nome_original = secure_filename(foto.filename)
            extensao = os.path.splitext(nome_original)[1]

            nome_arquivo = (
                f"baixa_{baixa.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}{extensao}"
            )

            caminho_salvar = os.path.join(pasta_upload, nome_arquivo)

            foto.save(caminho_salvar)

            legenda = legendas[i].strip() if i < len(legendas) else ""

            db.session.add(
                BaixaTecnicaFoto(
                    baixa_tecnica_id=baixa.id,
                    caminho_arquivo=f"uploads/baixas/{nome_arquivo}",
                    legenda=legenda
                )
            )

        for dados in itens_validos:
            item = Item.query.get(dados["item_id"])

            existente = (
                BaixaTecnicaItem.query
                .filter_by(
                    baixa_tecnica_id=baixa.id,
                    item_id=dados["item_id"],
                    tipo_estoque=dados["tipo_estoque"],
                    cliente_estoque_id=dados["cliente_estoque_id"]
                )
                .first()
            )

            if existente and existente.status in ["pendente", "pendente_ajuste"]:
                existente.quantidade = dados["quantidade"]
                existente.status = "pendente"

            else:
                db.session.add(
                    BaixaTecnicaItem(
                        baixa_tecnica_id=baixa.id,
                        item_id=dados["item_id"],
                        tipo_estoque=dados["tipo_estoque"],
                        cliente_estoque_id=dados["cliente_estoque_id"],
                        quantidade=dados["quantidade"],
                        quantidade_aprovada=0,
                        valor_unitario=float(item.valor or 0),
                        valor_total=(
                            float(dados["quantidade"] or 0)
                            * float(item.valor or 0)
                        ),
                        status="pendente"
                    )
                )

        db.session.commit()

        if baixa_existente:
            flash("Baixa corrigida e reenviada para aprovação.", "success")
        else:
            flash("Baixa enviada com sucesso. Aguarde aprovação.", "success")

    except Exception as e:
        db.session.rollback()
        print("ERRO BAIXA MOBILE:", e)
        flash("Erro ao registrar baixa.", "danger")

    return redirect(
        url_for(
            "baixa_tecnico.formulario_mobile_dedicado",
            tecnico_id=tecnico_id
        )
    )
    
    # ==========================================================
# BAIXAS PENDENTES MOBILE - APROVAÇÃO EM CAMPO
# ==========================================================

@bp_baixa_tecnico.route("/pendentes-mobile")
@login_required
def pendentes_mobile():

    baixas = (
        BaixaTecnica.query
        .filter_by(status="pendente")
        .order_by(BaixaTecnica.data_hora.desc())
        .all()
    )

    return render_template(
        "baixas_mobile/pendentes_aprovacao_mobile.html",
        baixas=baixas
    )


# ==========================================================
# DETALHE BAIXA PENDENTE MOBILE
# ==========================================================

@bp_baixa_tecnico.route("/detalhe-pendente-mobile/<int:baixa_id>")
@login_required
def detalhe_pendente_mobile(baixa_id):

    baixa = BaixaTecnica.query.get_or_404(baixa_id)

    return render_template(
        "baixas_mobile/detalhe_pendente_mobile.html",
        baixa=baixa
    )


# ==========================================================
# APROVAR BAIXA MOBILE
# ==========================================================

@bp_baixa_tecnico.route("/aprovar-mobile/<int:baixa_id>", methods=["POST"])
@login_required
def aprovar_mobile(baixa_id):

    baixa = BaixaTecnica.query.get_or_404(baixa_id)

    itens_pendentes = (
        BaixaTecnicaItem.query
        .filter(
            BaixaTecnicaItem.baixa_tecnica_id == baixa.id,
            BaixaTecnicaItem.status == "pendente"
        )
        .all()
    )

    if not itens_pendentes:
        flash("Nenhum item pendente encontrado para aprovação.", "warning")
        return redirect(
            url_for(
                "baixa_tecnico.detalhe_pendente_mobile",
                baixa_id=baixa.id
            )
        )

    try:

        for item_baixa in itens_pendentes:

            qtd_aprovar = int(item_baixa.quantidade or 0)

            if qtd_aprovar <= 0:
                continue

            cliente_ref = (
                item_baixa.cliente_estoque_id
                if item_baixa.tipo_estoque == "cliente"
                else baixa.cliente_id
            )

            saldo = (
                SaldoTecnico.query
                .filter(
                    SaldoTecnico.tecnico_id == baixa.tecnico_id,
                    SaldoTecnico.item_id == item_baixa.item_id,
                    SaldoTecnico.tipo_servico_id == baixa.tipo_servico_id,
                    SaldoTecnico.tipo_estoque == (item_baixa.tipo_estoque or "empresa"),
                    SaldoTecnico.cliente_id == cliente_ref,
                    SaldoTecnico.ordem_servico_id == baixa.ordem_servico_id
                )
                .first()
            )

            if not saldo:
                codigo = getattr(item_baixa.item, "codigo", item_baixa.item_id)
                flash(f"Saldo não encontrado para o item {codigo}.", "danger")
                return redirect(
                    url_for(
                        "baixa_tecnico.detalhe_pendente_mobile",
                        baixa_id=baixa.id
                    )
                )

            if int(saldo.quantidade or 0) < qtd_aprovar:
                codigo = getattr(item_baixa.item, "codigo", item_baixa.item_id)
                flash(f"Saldo insuficiente para o item {codigo}.", "danger")
                return redirect(
                    url_for(
                        "baixa_tecnico.detalhe_pendente_mobile",
                        baixa_id=baixa.id
                    )
                )

            saldo.quantidade -= qtd_aprovar

            item_baixa.quantidade_aprovada = (
                int(item_baixa.quantidade_aprovada or 0)
                + qtd_aprovar
            )

            item_baixa.quantidade = 0
            item_baixa.status = "confirmado"

        pendentes = (
            BaixaTecnicaItem.query
            .filter_by(
                baixa_tecnica_id=baixa.id,
                status="pendente"
            )
            .count()
        )

        if pendentes == 0:
            baixa.status = "confirmado"
            baixa.visualizado_tecnico = True
        else:
            baixa.status = "pendente"

        if baixa.cliente_id:
            cliente_os = Empresa.query.get(baixa.cliente_id)

            if cliente_os:
                baixas_abertas = (
                    BaixaTecnica.query
                    .filter(
                        BaixaTecnica.cliente_id == baixa.cliente_id,
                        BaixaTecnica.tecnico_id == baixa.tecnico_id,
                        BaixaTecnica.status.in_(["pendente", "pendente_ajuste"])
                    )
                    .count()
                )

                cliente_os.status_os = (
                    "finalizada"
                    if baixas_abertas == 0
                    else "em_andamento"
                )

        db.session.commit()

        flash("Baixa aprovada com sucesso.", "success")

    except Exception as e:
        db.session.rollback()
        print("ERRO APROVAR BAIXA MOBILE:", e)
        flash("Erro ao aprovar baixa.", "danger")

    return redirect(
        url_for("baixa_tecnico.pendentes_mobile")
    )

# ==========================================================
# RECUSAR / DEVOLVER BAIXA MOBILE
# ==========================================================

@bp_baixa_tecnico.route("/recusar-mobile/<int:baixa_id>", methods=["POST"])
@login_required
def recusar_mobile(baixa_id):

    baixa = BaixaTecnica.query.get_or_404(baixa_id)

    motivo = (
        request.form.get("motivo_recusa")
        or request.form.get("motivo")
        or ""
    ).strip()

    if not motivo:
        flash("Informe o motivo da devolução para ajuste.", "warning")
        return redirect(
            url_for(
                "baixa_tecnico.detalhe_pendente_mobile",
                baixa_id=baixa.id
            )
        )

    itens_devolvidos = (
        BaixaTecnicaItem.query
        .filter(
            BaixaTecnicaItem.baixa_tecnica_id == baixa.id,
            BaixaTecnicaItem.status == "pendente"
        )
        .all()
    )

    if not itens_devolvidos:
        flash("Nenhum item pendente encontrado para devolução.", "warning")
        return redirect(
            url_for(
                "baixa_tecnico.detalhe_pendente_mobile",
                baixa_id=baixa.id
            )
        )

    try:
        baixa.status = "pendente_ajuste"
        baixa.motivo_recusa = motivo
        baixa.visualizado_tecnico = False

        for item_baixa in itens_devolvidos:
            item_baixa.status = "pendente_ajuste"
            item_baixa.motivo_recusa = motivo

        if baixa.cliente_id:
            cliente_os = Empresa.query.get(baixa.cliente_id)

            if cliente_os:
                cliente_os.status_os = "em_andamento"

        db.session.commit()

        flash("Baixa devolvida para ajuste do técnico.", "warning")

    except Exception as e:
        db.session.rollback()
        print("ERRO RECUSAR BAIXA MOBILE:", e)
        flash("Erro ao devolver baixa para ajuste.", "danger")

    return redirect(
        url_for("baixa_tecnico.pendentes_mobile")
    )
    
   # ==========================================================
# LOGIN APROVADOR MOBILE
# ==========================================================

@bp_baixa_tecnico.route("/aprovador/login", methods=["GET", "POST"])
def login_aprovador_mobile():

    logout_user()
    session.clear()

    if request.method == "POST":

        email = request.form.get("login", "").strip()
        senha = request.form.get("senha", "").strip()

        usuario = (
            Usuario.query
            .filter(
                func.lower(Usuario.email) == email.lower()
            )
            .first()
        )

        if not usuario:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("baixa_tecnico.login_aprovador_mobile"))

        senha_ok = check_password_hash(usuario.senha_hash, senha)

        if not senha_ok:
            flash("Senha inválida.", "danger")
            return redirect(url_for("baixa_tecnico.login_aprovador_mobile"))

        if usuario.perfil not in ["admin", "tecnica", "engenheiro", "supervisor"]:
            flash("Usuário sem permissão para aprovar baixas.", "danger")
            return redirect(url_for("baixa_tecnico.login_aprovador_mobile"))

        login_user(usuario)

        session["portal_mobile_aprovador"] = True

        return redirect(url_for("baixa_tecnico.pendentes_mobile"))

    return render_template("baixas_mobile/login_aprovador.html")


