from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta
import io
import pandas as pd

from app.extensions import db
from app.models import (
    RequisicaoTecnico,
    RequisicaoTecnicoItem,
    Tecnico,
    TipoServico,
    Item,
    Estoque,
    SaldoTecnico
)


bp_requisicoes_tecnicos = Blueprint(
    "requisicoes_tecnicos", __name__, url_prefix="/requisicoes_tecnicos"
)

# ---------------------------------------------------------------------------
# NOVA REQUISIÇÃO -----------------------------------------------------------
# ---------------------------------------------------------------------------

@bp_requisicoes_tecnicos.route("/nova", methods=["GET", "POST"])
@login_required
def nova_requisicao():
    if request.method == "POST":
        dados = request.form

        # Buscar o tipo de serviço pelo ID e pegar o nome
        tipo_servico_id = dados.get("tipo_servico")
        tipo_servico_obj = TipoServico.query.get(tipo_servico_id)
        tipo_servico_nome = tipo_servico_obj.nome if tipo_servico_obj else ""

        nova = RequisicaoTecnico(
            solicitante_responsavel=dados.get("solicitante_responsavel"),
            resp_projeto=dados.get("resp_projeto"),
            solicitante_tecnico=dados.get("solicitante_tecnico"),
            tipo_servico=tipo_servico_nome,  # <-- salva o NOME
            observacao=dados.get("observacao"),
            status="pendente",
            data_hora=datetime.now()
        )
        db.session.add(nova)
        db.session.flush()

        for codigo, desc, unid, qtd, val, qtd_estoque in zip(
            dados.getlist("codigo[]"),
            dados.getlist("descricao[]"),
            dados.getlist("unidade[]"),
            dados.getlist("quantidade[]"),
            dados.getlist("valor[]"),
            dados.getlist("quantidade_estoque[]"),
        ):
            if codigo.strip():
                db.session.add(
                    RequisicaoTecnicoItem(
                        requisicao_id=nova.id,
                        codigo=codigo,
                        descricao=desc,
                        unidade=unid,
                        quantidade=int(qtd or 0),
                        valor=float(val or 0),
                        quantidade_estoque=int(qtd_estoque or 0),
                    )
                )

        db.session.commit()
        flash("Requisição cadastrada com sucesso!", "success")
        return redirect(url_for("requisicoes_tecnicos.recebidas"))

    tecnicos = Tecnico.query.order_by(Tecnico.nome).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()
    return render_template(
        "requisicoes_tecnicos/nova_requisicao.html",
        tecnicos=tecnicos,
        tipos_servico=tipos_servico,
    )

# ---------------------------------------------------------------------------
# LISTAGENS -----------------------------------------------------------------
# ---------------------------------------------------------------------------

@bp_requisicoes_tecnicos.route("/recebidas")
@login_required
def recebidas():
    requisicoes = (
        RequisicaoTecnico.query.filter_by(status="pendente")
        .order_by(RequisicaoTecnico.data_hora.desc())
        .all()
    )
    return render_template("requisicoes_tecnicos/recebidas.html", requisicoes=requisicoes)



@bp_requisicoes_tecnicos.route("/atendidas")
@login_required
def atendidas():
    requisicoes = (
        RequisicaoTecnico.query.filter_by(status="material_entregue")
        .order_by(RequisicaoTecnico.data_hora.desc())
        .all()
    )
    return render_template("requisicoes_tecnicos/atendidas.html", requisicoes=requisicoes)


@bp_requisicoes_tecnicos.route("/historico")
@login_required
def historico():
    requisicoes = (
        RequisicaoTecnico.query.order_by(RequisicaoTecnico.data_hora.desc()).all()
    )
    return render_template(
        "requisicoes_tecnicos/historico_requisicoes.html", requisicoes=requisicoes
    )
# ---------------------------------------------------------------------------
# API – Busca de Item por código -------------------------------------------
# ---------------------------------------------------------------------------

@bp_requisicoes_tecnicos.route("/api/item/<codigo>")
@login_required
def api_item_por_codigo(codigo):
    tipo_servico_nome = request.args.get("tipo_servico")
    if not tipo_servico_nome:
        return jsonify({"erro": "Tipo de serviço não informado"}), 400

    item = (
        Item.query.join(TipoServico)
        .filter(Item.codigo == codigo.strip(), TipoServico.nome == tipo_servico_nome)
        .first()
    )
    if not item:
        return jsonify({"erro": "Item não encontrado"}), 404

    estoque = Estoque.query.filter_by(item_id=item.id).first()
    qtd_estoque = estoque.quantidade if estoque else 0

    return jsonify(
        {
            "descricao": item.descricao,
            "unidade": item.unidade,
            "valor": item.valor,
            "quantidade_estoque": qtd_estoque,
        }
    )

# ---------------------------------------------------------------------------
# API – Itens por Tipo de Serviço -------------------------------------------
# ---------------------------------------------------------------------------

@bp_requisicoes_tecnicos.route("/api/itens_disponiveis")
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
            'quantidade_estoque': estoque.quantidade
        }
        for item, estoque in itens
    ])

# ---------------------------------------------------------------------------
# EXCLUIR -------------------------------------------------------------------
# ---------------------------------------------------------------------------

@bp_requisicoes_tecnicos.route("/nova-mobile/excluir/<int:index>")
@login_required
def excluir_item_temp(index):
    try:
        itens = session.get("itens_temp", [])
        if 0 <= index < len(itens):
            itens.pop(index)
            session["itens_temp"] = itens
            flash("Item removido com sucesso!", "info")
    except Exception as e:
        flash("Erro ao remover item.", "danger")

    tipo_servico = session.get("req_mobile_tipo_servico", "")
    return redirect(url_for('requisicoes_tecnicos.nova_requisicao_mobile', adicionado=1, tipo_servico=tipo_servico))


# ---------------------------------------------------------------------------
# RELATÓRIO DE CONSUMO ------------------------------------------------------
# ---------------------------------------------------------------------------

@bp_requisicoes_tecnicos.route("/relatorio-consumo", methods=["GET", "POST"])
@login_required
def relatorio_consumo():
    # Obtem todos os nomes distintos de técnicos diretamente do campo de texto
    nomes_tecnicos = db.session.query(RequisicaoTecnico.solicitante_tecnico).distinct().all()
    tecnicos = [nome[0] for nome in nomes_tecnicos]

    resultados = []
    filtros = {
        "tecnico": "todos",
        "codigo_item": "",
        "endereco": "",
        "data_inicio": "",
        "data_fim": ""
    }

    if request.method == "POST":
        tecnico_nome = request.form.get("tecnico")
        codigo_item = request.form.get("codigo_item")
        endereco = request.form.get("endereco")
        data_inicio_str = request.form.get("data_inicio")
        data_fim_str = request.form.get("data_fim")

        filtros["tecnico"] = tecnico_nome
        filtros["codigo_item"] = codigo_item
        filtros["endereco"] = endereco
        filtros["data_inicio"] = data_inicio_str
        filtros["data_fim"] = data_fim_str

        query = db.session.query(
            RequisicaoTecnico.solicitante_tecnico.label("nome_tecnico"),
            RequisicaoTecnicoItem.codigo,
            RequisicaoTecnicoItem.descricao,
            RequisicaoTecnicoItem.unidade,
            RequisicaoTecnico.endereco.label("endereco_servico"),
            func.sum(RequisicaoTecnicoItem.quantidade).label("quantidade_total"),
            RequisicaoTecnico.data_hora
        ).join(
            RequisicaoTecnicoItem, RequisicaoTecnico.id == RequisicaoTecnicoItem.requisicao_id
        ).filter(
            RequisicaoTecnico.status == "material_entregue"
        )

        if tecnico_nome and tecnico_nome != "todos":
            query = query.filter(RequisicaoTecnico.solicitante_tecnico == tecnico_nome)

        if codigo_item:
            query = query.filter(RequisicaoTecnicoItem.codigo.ilike(f"%{codigo_item}%"))

        if endereco:
            query = query.filter(RequisicaoTecnico.endereco.ilike(f"%{endereco}%"))

        # --- Tratamento das datas ---
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d")
                query = query.filter(RequisicaoTecnico.data_hora >= data_inicio)
            except ValueError:
                flash("Data de início inválida", "danger")

        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(RequisicaoTecnico.data_hora < data_fim)
            except ValueError:
                flash("Data final inválida", "danger")

        query = query.group_by(
            RequisicaoTecnico.solicitante_tecnico,
            RequisicaoTecnicoItem.codigo,
            RequisicaoTecnicoItem.descricao,
            RequisicaoTecnicoItem.unidade,
            RequisicaoTecnico.endereco,
            RequisicaoTecnico.data_hora
        ).order_by(
            RequisicaoTecnico.solicitante_tecnico,
            RequisicaoTecnicoItem.codigo,
            RequisicaoTecnico.data_hora
        )

        resultados = query.all()

    return render_template(
        "requisicoes_tecnicos/relatorio_consumo.html",
        tecnicos=tecnicos,
        resultados=resultados,
        filtros=filtros
    )

# ---------------------------------------------------------------------------
# FORMULÁRIO MOBILE ---------------------------------------------------------
# ---------------------------------------------------------------------------

@bp_requisicoes_tecnicos.route("/nova-mobile", methods=["GET", "POST"])
def nova_requisicao_mobile():
    if request.method == "POST":
        responsavel = request.form["solicitante_responsavel"]
        tecnico = request.form["solicitante_tecnico"]
        tipo_servico_id = request.form["tipo_servico"]
        resp_projeto = request.form.get("resp_projeto", "")
        observacao = request.form.get("observacao", "")

        # Buscar nome do tipo de serviço
        tipo_servico_obj = TipoServico.query.get(tipo_servico_id)
        tipo_servico_nome = tipo_servico_obj.nome if tipo_servico_obj else ""

        nova_requisicao = RequisicaoTecnico(
            solicitante_responsavel=responsavel,
            solicitante_tecnico=tecnico,
            tipo_servico=tipo_servico_nome,  # salva o nome
            resp_projeto=resp_projeto,
            observacao=observacao,
            status="pendente",
            data_hora=datetime.now(),
        )
        db.session.add(nova_requisicao)
        db.session.flush()

        codigos = request.form.getlist("codigo[]")
        descricoes = request.form.getlist("descricao[]")
        unidades = request.form.getlist("unidade[]")
        quantidades = request.form.getlist("quantidade[]")
        valores = request.form.getlist("valor[]")

        for i in range(len(codigos)):
            db.session.add(
                RequisicaoTecnicoItem(
                    requisicao_id=nova_requisicao.id,
                    codigo=codigos[i],
                    descricao=descricoes[i],
                    unidade=unidades[i],
                    quantidade=int(quantidades[i]),
                    valor=float(valores[i] or 0),
                )
            )

        db.session.commit()
        flash("Requisição enviada com sucesso!", "success")
        return redirect(url_for("requisicoes_tecnicos.nova_requisicao_mobile"))

    tecnicos = Tecnico.query.all()
    tipos_servico = TipoServico.query.all()
    return render_template(
        "requisicoes_tecnicos/nova_requisicao_mobile.html",
        tecnicos=tecnicos,
        tipos_servico=tipos_servico,
    )


# ---------------------------------------------------------------------------
# API – Contador de Requisições Pendentes ----------------------------------
# ---------------------------------------------------------------------------

@bp_requisicoes_tecnicos.route("/api/requisicoes/pendentes")
@login_required
def api_requisicoes_pendentes():
    if current_user.perfil in ["admin", "estoque", "tecnica"]:
        count = RequisicaoTecnico.query.filter_by(status="pendente").count()
        return jsonify({"count": count})
    return jsonify({"count": 0})

from app.models import SaldoTecnico  # certifique-se que está importado

@bp_requisicoes_tecnicos.route("/detalhes/<int:requisicao_id>", methods=["GET", "POST"])
@login_required
def detalhes(requisicao_id):
    requisicao = RequisicaoTecnico.query.get_or_404(requisicao_id)

    # Bloqueio de edição se já entregue
    status_bloqueado = requisicao.status == "material_entregue"

    # ---- CALCULAR SALDOS DO ESTOQUE ----
    tipo_servico = TipoServico.query.filter_by(nome=requisicao.tipo_servico).first()
    saldos = {}
    if tipo_servico:
        for item in requisicao.itens:
            estoque = (
                db.session.query(Estoque)
                .join(Item, Estoque.item_id == Item.id)
                .filter(Item.codigo == item.codigo, Estoque.tipo_servico_id == tipo_servico.id)
                .first()
            )
            saldos[item.codigo] = estoque.quantidade if estoque else 0
    else:
        for item in requisicao.itens:
            saldos[item.codigo] = 0

    # ---- POST (se permitido) ----
    if request.method == "POST" and not status_bloqueado:
        # Atualizar quantidades enviadas
        for item in requisicao.itens:
            nova_qtd = request.form.get(f"quantidade_{item.id}")
            if nova_qtd:
                item.quantidade = int(nova_qtd)

        requisicao.observacao_estoque = request.form.get("observacao_estoque") or ""
        novo_status = request.form.get("status")

        if novo_status == "material_entregue" and requisicao.status != "material_entregue":
            tecnico = Tecnico.query.filter_by(nome=requisicao.solicitante_tecnico).first()
            if not tecnico or not tipo_servico:
                flash("Técnico ou Tipo de Serviço inválido.", "danger")
                return redirect(url_for("requisicoes_tecnicos.detalhes", requisicao_id=requisicao.id))

            # Verificar estoque suficiente
            for item in requisicao.itens:
                estoque = (
                    db.session.query(Estoque)
                    .join(Item, Estoque.item_id == Item.id)
                    .filter(Item.codigo == item.codigo, Estoque.tipo_servico_id == tipo_servico.id)
                    .first()
                )
                if not estoque or estoque.quantidade < item.quantidade:
                    flash(f"Estoque insuficiente para o item {item.codigo}.", "danger")
                    return redirect(url_for("requisicoes_tecnicos.detalhes", requisicao_id=requisicao.id))

            # Debitar estoque e creditar saldo técnico
            for item in requisicao.itens:
                item_obj = Item.query.filter_by(codigo=item.codigo).first()
                estoque = (
                    db.session.query(Estoque)
                    .join(Item, Estoque.item_id == Item.id)
                    .filter(Item.codigo == item.codigo, Estoque.tipo_servico_id == tipo_servico.id)
                    .first()
                )
                estoque.quantidade -= item.quantidade

                saldo = SaldoTecnico.query.filter_by(
                    tecnico_id=tecnico.id,
                    item_id=item_obj.id,
                    tipo_servico_id=tipo_servico.id
                ).first()
                if saldo:
                    saldo.quantidade += item.quantidade
                else:
                    saldo = SaldoTecnico(
                        tecnico_id=tecnico.id,
                        item_id=item_obj.id,
                        tipo_servico_id=tipo_servico.id,
                        quantidade=item.quantidade
                    )
                    db.session.add(saldo)

        requisicao.status = novo_status
        db.session.commit()
        flash("Requisição atualizada com sucesso ✅", "success")
        return redirect(url_for("requisicoes_tecnicos.recebidas"))

    return render_template(
        "requisicoes_tecnicos/detalhes_requisicao.html",
        requisicao=requisicao,
        status_bloqueado=status_bloqueado,
        saldos=saldos
    )
    
@bp_requisicoes_tecnicos.route("/historico/detalhes/<int:requisicao_id>")
@login_required
def historico_detalhes(requisicao_id):
    requisicao = RequisicaoTecnico.query.get_or_404(requisicao_id)
    tipo_servico = TipoServico.query.filter_by(nome=requisicao.tipo_servico).first()

    # calcular saldos
    saldos = {}
    if tipo_servico:
        for item in requisicao.itens:
            estoque = (
                db.session.query(Estoque)
                .join(Item, Estoque.item_id == Item.id)
                .filter(Item.codigo == item.codigo,
                        Estoque.tipo_servico_id == tipo_servico.id)
                .first()
            )
            saldos[item.codigo] = estoque.quantidade if estoque else 0

    # renderizar com campos bloqueados
    return render_template(
        "requisicoes_tecnicos/detalhes_requisicao.html",
        requisicao=requisicao,
        saldos=saldos,
        status_bloqueado=True  # força modo somente leitura
    )


@bp_requisicoes_tecnicos.route("/relatorio-consumo/exportar-excel", methods=["POST"])
@login_required
def exportar_excel_relatorio_consumo():
    from io import BytesIO
    import pandas as pd
    from flask import send_file

    tecnico_nome = request.form.get("tecnico")
    codigo_item = request.form.get("codigo_item")
    endereco = request.form.get("endereco")
    data_inicio = request.form.get("data_inicio")
    data_fim = request.form.get("data_fim")

    query = db.session.query(
        RequisicaoTecnico.solicitante_tecnico.label("Técnico"),
        RequisicaoTecnicoItem.codigo.label("Código"),
        RequisicaoTecnicoItem.descricao.label("Descrição"),
        RequisicaoTecnicoItem.unidade.label("Unidade"),
        func.sum(RequisicaoTecnicoItem.quantidade).label("Quantidade"),
        RequisicaoTecnico.data_hora.label("Data")
    ).join(
        RequisicaoTecnicoItem, RequisicaoTecnico.id == RequisicaoTecnicoItem.requisicao_id
    ).filter(
        RequisicaoTecnico.status == "material_entregue"
    )

    if tecnico_nome and tecnico_nome != "todos":
        query = query.filter(RequisicaoTecnico.solicitante_tecnico == tecnico_nome)

    if codigo_item:
        query = query.filter(RequisicaoTecnicoItem.codigo.ilike(f"%{codigo_item}%"))

    if endereco:
        query = query.filter(RequisicaoTecnico.endereco.ilike(f"%{endereco}%"))

    if data_inicio:
        try:
            data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            query = query.filter(RequisicaoTecnico.data_hora >= data_inicio)
        except ValueError:
            pass

    if data_fim:
        try:
            data_fim = datetime.strptime(data_fim, "%Y-%m-%d")
            query = query.filter(RequisicaoTecnico.data_hora <= data_fim)
        except ValueError:
            pass

    query = query.group_by(
        RequisicaoTecnico.solicitante_tecnico,
        RequisicaoTecnicoItem.codigo,
        RequisicaoTecnicoItem.descricao,
        RequisicaoTecnicoItem.unidade,
        RequisicaoTecnico.data_hora
    ).order_by(
        RequisicaoTecnico.solicitante_tecnico,
        RequisicaoTecnicoItem.codigo,
        RequisicaoTecnico.data_hora
    )

    resultados = query.all()

    df = pd.DataFrame([r._asdict() for r in resultados])
    if not df.empty:
        df["Data"] = df["Data"].dt.strftime("%d/%m/%Y %H:%M")

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output,
                     download_name="relatorio_consumo_tecnico.xlsx",
                     as_attachment=True,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp_requisicoes_tecnicos.route("/mobile")
def mobile_home():
    return render_template("baixa_tecnico/mobile_home.html")

# --- NOVA ROTA PARA VERSÃO MOBILE RECEBIDAS ---
@bp_requisicoes_tecnicos.route("/mobile/recebidas", methods=["GET"])
def mobile_recebidas():
    requisicoes = (
        RequisicaoTecnico.query.filter_by(status="pendente")
        .order_by(RequisicaoTecnico.data_hora.desc())
        .all()
    )

    saldos_estoque = {}
    saldos_tecnico = {}
    for req in requisicoes:
        tipo_servico = TipoServico.query.filter_by(nome=req.tipo_servico).first()
        tecnico = Tecnico.query.filter_by(nome=req.solicitante_tecnico).first()

        saldos_estoque[req.id] = {}
        saldos_tecnico[req.id] = {}

        for item in req.itens:
            estoque = None
            saldo = None

            # Se tipo_servico encontrado
            if tipo_servico:
                estoque = (
                    Estoque.query.join(Item)
                    .filter(Item.codigo == item.codigo,
                            Estoque.tipo_servico_id == tipo_servico.id)
                    .first()
                )
            # Se tecnico encontrado e tipo_servico encontrado
            if tecnico and tipo_servico:
                saldo = (
                    SaldoTecnico.query.join(Item)
                    .filter(SaldoTecnico.tecnico_id == tecnico.id,
                            Item.codigo == item.codigo,
                            SaldoTecnico.tipo_servico_id == tipo_servico.id)
                    .first()
                )

            saldos_estoque[req.id][item.codigo] = estoque.quantidade if estoque else 0
            saldos_tecnico[req.id][item.codigo] = saldo.quantidade if saldo else 0

    return render_template(
        "requisicoes_tecnicos/mobile_recebidas.html",
        requisicoes=requisicoes,
        saldos_estoque=saldos_estoque,
        saldos_tecnico=saldos_tecnico
    )

# --- NOVA ROTA PARA DETALHES COM ASSINATURA ---
@bp_requisicoes_tecnicos.route("/mobile/detalhes/<int:requisicao_id>", methods=["GET", "POST"])
def mobile_detalhes(requisicao_id):
    requisicao = RequisicaoTecnico.query.get_or_404(requisicao_id)

    tipo_servico = TipoServico.query.filter_by(nome=requisicao.tipo_servico).first()
    tecnico = Tecnico.query.filter_by(nome=requisicao.solicitante_tecnico).first()

    # --- SALDOS E ENDEREÇOS ---
    saldos_estoque = {}
    saldos_tecnico = {}
    enderecos_itens = {}

    for item in requisicao.itens:
        # Estoque do item
        estoque = (Estoque.query.join(Item)
                   .filter(Item.codigo == item.codigo,
                           Estoque.tipo_servico_id == tipo_servico.id)
                   .first())
        saldo_tecnico = (SaldoTecnico.query.join(Item)
                         .filter(SaldoTecnico.tecnico_id == tecnico.id,
                                 Item.codigo == item.codigo,
                                 SaldoTecnico.tipo_servico_id == tipo_servico.id)
                         .first())

        saldos_estoque[item.codigo] = estoque.quantidade if estoque else 0
        saldos_tecnico[item.codigo] = saldo_tecnico.quantidade if saldo_tecnico else 0
        enderecos_itens[item.codigo] = estoque.endereco if estoque and estoque.endereco else "-"

    # --- POST COM ASSINATURA ---
    if request.method == "POST":
        assinatura_base64 = request.form.get("assinatura")
        if assinatura_base64:
            import base64, os
            from datetime import datetime

            assinatura_data = assinatura_base64.split(",")[1]
            imagem_bytes = base64.b64decode(assinatura_data)
            pasta_assinaturas = os.path.join("app", "static", "assinaturas")
            os.makedirs(pasta_assinaturas, exist_ok=True)
            filename = f"assinatura_{requisicao.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            filepath = os.path.join(pasta_assinaturas, filename)
            with open(filepath, "wb") as f:
                f.write(imagem_bytes)

            requisicao.assinatura_path = f"assinaturas/{filename}"

        requisicao.status = "material_entregue"
        db.session.commit()

        flash("Requisição finalizada com assinatura do técnico.", "success")
        return redirect(url_for("requisicoes_tecnicos.mobile_recebidas"))

    return render_template(
        "requisicoes_tecnicos/mobile_detalhes.html",
        requisicao=requisicao,
        saldos_estoque=saldos_estoque,
        saldos_tecnico=saldos_tecnico,
        enderecos_itens=enderecos_itens,  # <-- AQUI
        entregue=(requisicao.status == "material_entregue")
    )
    
@bp_requisicoes_tecnicos.route("/api/pendentes_count")
def api_pendentes_count():
    count = RequisicaoTecnico.query.filter_by(status="pendente").count()
    return jsonify({"pendentes": count})

