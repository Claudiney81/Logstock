from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app, send_file
)
from flask_login import login_required, current_user
from datetime import datetime
import os
import base64
from io import BytesIO

from app.extensions import db
from app.models import (
    RequisicaoTecnico,
    RequisicaoTecnicoItem,
    Tecnico,
    TipoServico,
    Item,
    Estoque,
    SaldoTecnico,
    Empresa
)

from app.utils.mailer import send_requisition_email, _build_requisition_pdf


bp_requisicoes_tecnicos = Blueprint(
    "requisicoes_tecnicos",
    __name__,
    url_prefix="/requisicoes_tecnicos"
)


# ==========================================================
# HELPERS
# ==========================================================

def get_nome_usuario():
    return (
        getattr(current_user, "nome", None)
        or getattr(current_user, "email", None)
        or "Usuário"
    )


def get_tecnico_logado():
    tecnico_id = getattr(current_user, "tecnico_id", None)

    if tecnico_id:
        tecnico = Tecnico.query.get(tecnico_id)
        if tecnico:
            return tecnico

    email = getattr(current_user, "email", None)

    if email and hasattr(Tecnico, "email"):
        tecnico = Tecnico.query.filter_by(email=email).first()
        if tecnico:
            return tecnico

    nome = get_nome_usuario()
    return Tecnico.query.filter_by(nome=nome).first()


def usuario_atendente():
    perfil = getattr(current_user, "perfil", "")
    return perfil in ["admin", "estoque", "tecnica", "supervisor"]


def salvar_assinatura(assinatura_base64, requisicao_id, origem="mobile"):
    if not assinatura_base64:
        return None

    try:
        if "," in assinatura_base64:
            assinatura_data = assinatura_base64.split(",", 1)[1]
        else:
            assinatura_data = assinatura_base64

        imagem_bytes = base64.b64decode(assinatura_data)

        pasta = os.path.join("app", "static", "assinaturas")
        os.makedirs(pasta, exist_ok=True)

        nome = f"assinatura_{origem}_{requisicao_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        caminho = os.path.join(pasta, nome)

        with open(caminho, "wb") as f:
            f.write(imagem_bytes)

        return f"assinaturas/{nome}"

    except Exception as e:
        current_app.logger.exception("Erro ao salvar assinatura: %s", e)
        return None


def get_tipo_servico(requisicao):
    return TipoServico.query.filter_by(nome=requisicao.tipo_servico).first()


def get_tecnico_requisicao(requisicao):
    if requisicao.solicitante_tecnico_id:
        tecnico = Tecnico.query.get(requisicao.solicitante_tecnico_id)
        if tecnico:
            return tecnico

    return Tecnico.query.filter_by(
        nome=(requisicao.solicitante_tecnico or "").strip()
    ).first()


def buscar_estoque(item_db, tipo_servico_id, tipo_estoque="empresa", cliente_id=None):
    query = Estoque.query.filter(
        Estoque.item_id == item_db.id,
        Estoque.tipo_servico_id == tipo_servico_id
    )

    if hasattr(Estoque, "tipo_estoque"):
        query = query.filter(Estoque.tipo_estoque == tipo_estoque)

    if hasattr(Estoque, "cliente_id"):
        if tipo_estoque == "cliente":
            query = query.filter(Estoque.cliente_id == cliente_id)
        else:
            query = query.filter(Estoque.cliente_id.is_(None))

    return query.first()


def carregar_saldos(requisicao):
    tipo_servico = get_tipo_servico(requisicao)
    tecnico = get_tecnico_requisicao(requisicao)
    tipo_servico_saldo_id = 1

    saldos_estoque = {}
    saldos_tecnico = {}
    enderecos_itens = {}

    tipo_estoque = requisicao.tipo_estoque or "empresa"
    cliente_id = requisicao.cliente_id

    for item_req in requisicao.itens:
        saldos_estoque[item_req.codigo] = 0
        saldos_tecnico[item_req.codigo] = 0
        enderecos_itens[item_req.codigo] = "-"

        item_db = Item.query.filter_by(codigo=item_req.codigo).first()

        if not item_db or not tipo_servico:
            continue

        estoque = buscar_estoque(
            item_db=item_db,
            tipo_servico_id=tipo_servico_saldo_id,
            tipo_estoque=tipo_estoque,
            cliente_id=cliente_id
        )

        if estoque:
            saldos_estoque[item_req.codigo] = estoque.quantidade or 0
            enderecos_itens[item_req.codigo] = estoque.endereco or "-"

        if tecnico:
            saldo = SaldoTecnico.query.filter_by(
                tecnico_id=tecnico.id,
                item_id=item_db.id,
                tipo_servico_id=tipo_servico_saldo_id
            ).first()

            saldos_tecnico[item_req.codigo] = saldo.quantidade if saldo else 0

    return saldos_estoque, saldos_tecnico, enderecos_itens


def criar_itens_requisicao(requisicao_id):
    codigos = request.form.getlist("codigo[]")
    descricoes = request.form.getlist("descricao[]")
    unidades = request.form.getlist("unidade[]")
    quantidades = request.form.getlist("quantidade[]")
    valores = request.form.getlist("valor[]")

    total = 0

    for i in range(len(codigos)):
        codigo = (codigos[i] or "").strip()

        if not codigo:
            continue

        try:
            quantidade = int(quantidades[i] or 0)
        except Exception:
            quantidade = 0

        if quantidade <= 0:
            continue

        try:
            valor = float(str(valores[i] or "0").replace(",", "."))
        except Exception:
            valor = 0.0

        item = RequisicaoTecnicoItem(
            requisicao_id=requisicao_id,
            codigo=codigo,
            descricao=descricoes[i] if i < len(descricoes) else "",
            unidade=unidades[i] if i < len(unidades) else "",
            quantidade=quantidade,
            valor=valor
        )

        db.session.add(item)
        total += 1

    return total


def movimentar_para_saldo_tecnico(requisicao):
    tipo_servico = get_tipo_servico(requisicao)
    tecnico = get_tecnico_requisicao(requisicao)

    # REGRA LOGISTOCK:
    # A requisição continua registrada como Manutenção/Reparo/Instalação,
    # mas o saldo físico sempre é debitado e creditado em Instalação.
    tipo_servico_saldo_id = 1

    if not tipo_servico:
        return False, "Tipo de serviço inválido."

    if not tecnico:
        return False, "Técnico inválido."

    tipo_estoque = requisicao.tipo_estoque or "empresa"
    cliente_id = requisicao.cliente_id

    for item_req in requisicao.itens:
        item_db = Item.query.filter_by(codigo=item_req.codigo).first()

        if not item_db:
            return False, f"Item {item_req.codigo} não encontrado."

        estoque = buscar_estoque(
            item_db=item_db,
            tipo_servico_id=tipo_servico_saldo_id,
            tipo_estoque=tipo_estoque,
            cliente_id=cliente_id
        )

        if not estoque:
            return False, f"Estoque não encontrado para o item {item_req.codigo}."

        if (estoque.quantidade or 0) < (item_req.quantidade or 0):
            return False, f"Estoque insuficiente para o item {item_req.codigo}."

    for item_req in requisicao.itens:
        item_db = Item.query.filter_by(codigo=item_req.codigo).first()

        estoque = buscar_estoque(
            item_db=item_db,
            tipo_servico_id=tipo_servico_saldo_id,
            tipo_estoque=tipo_estoque,
            cliente_id=cliente_id
        )

        estoque.quantidade -= item_req.quantidade

        saldo = SaldoTecnico.query.filter_by(
            tecnico_id=tecnico.id,
            item_id=item_db.id,
            tipo_servico_id=tipo_servico_saldo_id
        ).first()

        if saldo:
            saldo.quantidade += item_req.quantidade
            saldo.tipo_estoque = tipo_estoque
            saldo.cliente_id = cliente_id
            saldo.valor_unitario = float(estoque.valor_unitario or item_db.valor or 0)
            saldo.endereco = requisicao.endereco
            saldo.bairro = requisicao.bairro
            saldo.codigo_imovel = requisicao.codigo_imovel
        else:
            novo_saldo = SaldoTecnico(
                tecnico_id=tecnico.id,
                item_id=item_db.id,
                tipo_servico_id=tipo_servico_saldo_id,
                quantidade=item_req.quantidade,
                valor_unitario=float(estoque.valor_unitario or item_db.valor or 0),
                tipo_estoque=tipo_estoque,
                cliente_id=cliente_id,
                endereco=requisicao.endereco,
                bairro=requisicao.bairro,
                codigo_imovel=requisicao.codigo_imovel
            )
            db.session.add(novo_saldo)

    return True, "Movimentação realizada com sucesso."

# ==========================================================
# NOVA REQUISIÇÃO MOBILE
# técnico logado cria requisição
# tipo_estoque sempre começa como EMPRESA
# ==========================================================

@bp_requisicoes_tecnicos.route("/nova-mobile", methods=["GET", "POST"])
@login_required
def nova_requisicao_mobile():
    tecnico = get_tecnico_logado()

    if not tecnico:
        flash("Não foi possível localizar o técnico vinculado ao login.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        tipo_servico_id = request.form.get("tipo_servico", type=int)
        cliente_id = request.form.get("cliente_id", type=int)
        endereco = request.form.get("endereco", "").strip()
        observacao = request.form.get("observacao", "").strip() or "N/D"

        tipo_servico = TipoServico.query.get(tipo_servico_id)
        cliente = Empresa.query.get(cliente_id) if cliente_id else None

        if not tipo_servico:
            flash("Selecione o tipo de serviço.", "warning")
            return redirect(url_for("requisicoes_tecnicos.nova_requisicao_mobile"))

        if not cliente:
            flash("Selecione o Cliente / O.S.", "warning")
            return redirect(url_for("requisicoes_tecnicos.nova_requisicao_mobile"))

        if not endereco:
            flash("Informe o endereço.", "warning")
            return redirect(url_for("requisicoes_tecnicos.nova_requisicao_mobile"))

        requisicao = RequisicaoTecnico(
            solicitante_responsavel=tecnico.nome,
            solicitante_tecnico=tecnico.nome,
            solicitante_tecnico_id=tecnico.id,
            tipo_estoque="empresa",
            cliente_id=cliente.id,
            os_cliente=getattr(cliente, "razao_social", ""),
            tipo_servico=tipo_servico.nome,
            endereco=endereco,
            observacao=observacao,
            origem_mobile=True,
            status="pendente",
            data_hora=datetime.now()
        )

        db.session.add(requisicao)
        db.session.flush()

        total_itens = criar_itens_requisicao(requisicao.id)

        if total_itens == 0:
            db.session.rollback()
            flash("Adicione pelo menos um item com quantidade maior que zero.", "warning")
            return redirect(url_for("requisicoes_tecnicos.nova_requisicao_mobile"))

        db.session.commit()

        flash("Requisição enviada com sucesso.", "success")
        return redirect(url_for("requisicoes_tecnicos.mobile_recebidas"))

    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()
    clientes = Empresa.query.order_by(Empresa.razao_social).all()

    return render_template(
    "requisicao_mobile/nova.html",
    tecnico=tecnico,
    tecnico_logado=tecnico,
    tipos_servico=tipos_servico,
    clientes=clientes,
    tipo_estoque_padrao="empresa"
    )


# ==========================================================
# RECEBIDAS MOBILE
# atendente vê somente requisições mobile pendentes
# ==========================================================

@bp_requisicoes_tecnicos.route("/mobile/recebidas")
@login_required
def mobile_recebidas():
    requisicoes = (
        RequisicaoTecnico.query
        .filter(
            RequisicaoTecnico.origem_mobile == True,
            RequisicaoTecnico.status == "pendente"
        )
        .order_by(RequisicaoTecnico.data_hora.desc())
        .all()
    )

    return render_template(
        "requisicao_mobile/recebidas.html",
        requisicoes=requisicoes
    )


# ==========================================================
# DETALHES / ATENDIMENTO MOBILE
# atendente pode ajustar tipo_estoque e finalizar
# ==========================================================

@bp_requisicoes_tecnicos.route("/mobile/detalhes/<int:requisicao_id>", methods=["GET", "POST"])
@login_required
def mobile_detalhes(requisicao_id):
    requisicao = RequisicaoTecnico.query.get_or_404(requisicao_id)

    if request.method == "POST":
        if requisicao.status == "material_entregue":
            flash("Esta requisição já foi finalizada.", "info")
            return redirect(url_for("requisicoes_tecnicos.mobile_recebidas"))

        tipo_estoque = request.form.get("tipo_estoque") or requisicao.tipo_estoque or "empresa"
        cliente_id = request.form.get("cliente_id", type=int)
        observacao_estoque = request.form.get("observacao_estoque", "").strip() or "N/D"
        novo_status = request.form.get("status") or "pendente"

        if tipo_estoque not in ["empresa", "cliente"]:
            tipo_estoque = "empresa"

        if tipo_estoque == "cliente" and not cliente_id:
            flash("Selecione o Cliente / O.S para atender pelo estoque do cliente.", "warning")
            return redirect(url_for("requisicoes_tecnicos.mobile_detalhes", requisicao_id=requisicao.id))

        requisicao.tipo_estoque = tipo_estoque
        requisicao.cliente_id = cliente_id if tipo_estoque == "cliente" else requisicao.cliente_id
        requisicao.observacao_estoque = observacao_estoque

        for item in requisicao.itens:
            nova_qtd = request.form.get(f"quantidade_{item.id}")

            if nova_qtd:
                try:
                    qtd = int(nova_qtd)
                    if qtd >= 0:
                        item.quantidade = qtd
                except Exception:
                    pass

        assinatura_base64 = (
            request.form.get("assinatura_base64")
            or request.form.get("assinatura")
        )

        if novo_status == "material_entregue":
            if assinatura_base64:
                caminho = salvar_assinatura(
                    assinatura_base64,
                    requisicao.id,
                    "mobile"
                )

                if caminho:
                    requisicao.assinatura_path = caminho
                    requisicao.assinatura_base64 = assinatura_base64

            ok, msg = movimentar_para_saldo_tecnico(requisicao)

            if not ok:
                db.session.rollback()
                flash(msg, "danger")
                return redirect(url_for("requisicoes_tecnicos.mobile_detalhes", requisicao_id=requisicao.id))

            requisicao.status = "material_entregue"

        db.session.commit()

        if requisicao.status == "material_entregue":
            try:
                enviado = send_requisition_email(requisicao, attach_pdf=True)

                if enviado:
                    flash("Requisição finalizada e enviada ao e-mail do técnico.", "success")
                else:
                    flash("Requisição finalizada, mas o e-mail não foi enviado.", "warning")

            except Exception:
                current_app.logger.exception("Erro ao enviar e-mail")
                flash("Material entregue, mas ocorreu erro ao enviar e-mail.", "warning")

            return redirect(url_for("requisicoes_tecnicos.historico"))

        flash("Requisição atualizada com sucesso.", "success")
        return redirect(url_for("requisicoes_tecnicos.mobile_recebidas"))

    saldos_estoque, saldos_tecnico, enderecos_itens = carregar_saldos(requisicao)
    clientes = Empresa.query.order_by(Empresa.razao_social).all()

    return render_template(
        "requisicao_mobile/atender.html",
        requisicao=requisicao,
        itens=requisicao.itens,
        saldos_estoque=saldos_estoque,
        saldos_tecnico=saldos_tecnico,
        enderecos_itens=enderecos_itens,
        clientes=clientes,
        status_bloqueado=False
    )

# ==========================================================
# HISTÓRICO
# ==========================================================

@bp_requisicoes_tecnicos.route("/historico")
@login_required
def historico():

    tecnico = request.args.get("tecnico", "").strip()
    cliente = request.args.get("cliente", "").strip()
    status = request.args.get("status", "").strip()
    data = request.args.get("data", "").strip()

    query = (
        RequisicaoTecnico.query
        .filter(RequisicaoTecnico.origem_mobile == True)
    )

    # TÉCNICO
    if tecnico:
        query = query.filter(
            RequisicaoTecnico.solicitante_tecnico.ilike(f"%{tecnico}%")
        )

    # CLIENTE / O.S
    if cliente:
        query = query.filter(
            RequisicaoTecnico.os_cliente.ilike(f"%{cliente}%")
        )

    # STATUS
    if status:
        query = query.filter(
            RequisicaoTecnico.status == status
        )

    # DATA
    if data:
        query = query.filter(
            db.func.date(RequisicaoTecnico.data_hora) == data
        )

    requisicoes = (
        query
        .order_by(RequisicaoTecnico.data_hora.desc())
        .all()
    )

    return render_template(
        "requisicao_mobile/historico.html",
        requisicoes=requisicoes
    )

@bp_requisicoes_tecnicos.route("/historico/detalhes/<int:requisicao_id>")
@login_required
def historico_detalhes(requisicao_id):
    requisicao = RequisicaoTecnico.query.get_or_404(requisicao_id)

    saldos_estoque, saldos_tecnico, enderecos_itens = carregar_saldos(requisicao)
    clientes = Empresa.query.order_by(Empresa.razao_social).all()

    return render_template(
        "requisicao_mobile/detalhes.html",
        requisicao=requisicao,
        status_bloqueado=True,
        saldos_estoque=saldos_estoque,
        saldos_tecnico=saldos_tecnico,
        enderecos_itens=enderecos_itens,
        clientes=clientes
    )


@bp_requisicoes_tecnicos.route("/mobile/detalhes/<int:requisicao_id>/pdf")
@bp_requisicoes_tecnicos.route("/historico/detalhes/<int:requisicao_id>/pdf")
@login_required
def historico_detalhes_pdf(requisicao_id):
    requisicao = RequisicaoTecnico.query.get_or_404(requisicao_id)

    pdf_bytes = _build_requisition_pdf(requisicao)

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"comprovante_requisicao_{requisicao.id}.pdf"
    )

# ==========================================================
# API ITENS DISPONÍVEIS
# usada no formulário mobile para adicionar itens
# ==========================================================

@bp_requisicoes_tecnicos.route("/api/itens_disponiveis")
@login_required
def api_itens_disponiveis():
    tipo_servico_id = request.args.get("tipo_servico_id", type=int)
    tipo_estoque = request.args.get("tipo_estoque") or "empresa"
    cliente_id = request.args.get("cliente_id", type=int)

    if not tipo_servico_id:
        return jsonify([])

    # REGRA LOGISTOCK:
    # Manutenção/Reparo usam o saldo físico da Instalação.
    tipo_servico_saldo_id = 1

    query = (
        db.session.query(Item, Estoque)
        .join(Estoque, Item.id == Estoque.item_id)
        .filter(
            Estoque.tipo_servico_id == tipo_servico_saldo_id,
            Estoque.quantidade > 0
        )
    )

    if hasattr(Estoque, "tipo_estoque"):
        query = query.filter(Estoque.tipo_estoque == tipo_estoque)

    if hasattr(Estoque, "cliente_id"):
        if tipo_estoque == "cliente":
            query = query.filter(Estoque.cliente_id == cliente_id)
        else:
            query = query.filter(Estoque.cliente_id.is_(None))

    itens = query.order_by(Item.descricao).all()

    return jsonify([
        {
            "codigo": item.codigo,
            "descricao": item.descricao,
            "unidade": item.unidade,
            "valor": float(estoque.valor_unitario or item.valor or 0),
            "quantidade_estoque": estoque.quantidade
        }
        for item, estoque in itens
    ])


# ==========================================================
# API CONTADOR PENDENTES
# badge vermelho no menu
# ==========================================================

@bp_requisicoes_tecnicos.route("/api/requisicoes/pendentes")
@login_required
def api_requisicoes_pendentes():

    count = (
        RequisicaoTecnico.query
        .filter(
            RequisicaoTecnico.origem_mobile == True,
            RequisicaoTecnico.status == "pendente"
        )
        .count()
    )

    return jsonify({"count": count})


@bp_requisicoes_tecnicos.route("/api/pendentes_count")
@login_required
def api_pendentes_count():
    count = (
        RequisicaoTecnico.query
        .filter(
            RequisicaoTecnico.origem_mobile == True,
            RequisicaoTecnico.status == "pendente"
        )
        .count()
    )

    return jsonify({"pendentes": count})


# ==========================================================
# HOME MOBILE
# ==========================================================

@bp_requisicoes_tecnicos.route("/mobile")
@login_required
def mobile_home():
    return redirect(url_for("requisicoes_tecnicos.mobile_recebidas"))
