from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    current_app,
    send_file
)

from flask_login import login_required

from datetime import datetime

import io
import pandas as pd

from sqlalchemy import func, or_

import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from app.extensions import db

from app.models import (
    Item,
    Estoque,
    Tecnico,
    EquipamentoTecnico,
    HistoricoEquipamento,
    HistoricoEquipamentoItem,
)


bp_ferramentas_epis = Blueprint(
    "ferramentas_epis",
    __name__,
    url_prefix="/ferramentas-epis"
)


# ==========================================================
# HELPERS
# ==========================================================

MOTIVOS_RETORNO = [
    "devolucao",
    "troca",
    "extravio",
    "perda",
    "desgaste",
    "mau_uso"
]


def normalizar_categoria(categoria):
    return (categoria or "").strip().upper()


def item_valor(item):
    return float(getattr(item, "valor", 0) or 0)


def buscar_estoque_empresa(item_id):
    return (
        Estoque.query
        .filter(
            Estoque.item_id == item_id,
            Estoque.tipo_estoque == "empresa"
        )
        .first()
    ) or Estoque.query.filter_by(item_id=item_id).first()


def debitar_estoque_empresa(item_id, quantidade):
    estoque = buscar_estoque_empresa(item_id)

    if not estoque or (estoque.quantidade or 0) < quantidade:
        return False

    estoque.quantidade -= quantidade
    return True


def creditar_estoque_empresa(item_id, quantidade):
    estoque = buscar_estoque_empresa(item_id)

    if estoque:
        estoque.quantidade = (estoque.quantidade or 0) + quantidade
    else:
        estoque = Estoque(
            item_id=item_id,
            quantidade=quantidade,
            tipo_estoque="empresa"
        )
        db.session.add(estoque)

    return estoque


def remover_posse_tecnico(item_id, tecnico_id, quantidade, novo_status, motivo=None):
    registros = (
        EquipamentoTecnico.query
        .filter_by(
            item_id=item_id,
            tecnico_id=tecnico_id,
            status="tecnico"
        )
        .order_by(EquipamentoTecnico.data_hora.asc())
        .all()
    )

    saldo_total = sum(r.quantidade or 0 for r in registros)

    if saldo_total < quantidade:
        return False

    restante = quantidade

    for reg in registros:
        if restante <= 0:
            break

        qtd_reg = reg.quantidade or 0

        if qtd_reg <= restante:
            reg.status = novo_status
            reg.local = motivo or novo_status
            reg.data_hora = datetime.utcnow()
            restante -= qtd_reg

        else:
            reg.quantidade = qtd_reg - restante

            novo = EquipamentoTecnico(
                item_id=reg.item_id,
                tecnico_id=reg.tecnico_id,
                categoria=reg.categoria,
                local=motivo or novo_status,
                status=novo_status,
                quantidade=restante,
                valor_unitario=reg.valor_unitario,
                valor_total=(reg.valor_unitario or 0) * restante,
                data_hora=datetime.utcnow()
            )

            db.session.add(novo)
            restante = 0

    return True


# ==========================================================
# TRANSFERÊNCIA - SAÍDA / RETORNO - MÚLTIPLOS ITENS
# ==========================================================

@bp_ferramentas_epis.route("/transferencia", methods=["GET", "POST"])
@login_required
def transferencia():
    tecnicos = Tecnico.query.order_by(Tecnico.nome.asc()).all()

    itens = (
        Item.query
        .filter(Item.categoria.in_(["FERRAMENTA", "EPI", "ferramenta", "epi"]))
        .order_by(Item.descricao.asc())
        .all()
    )

    if request.method == "POST":
        tipo_transferencia = request.form.get("tipo_transferencia")
        tecnico_id = request.form.get("tecnico_id")
        motivo_retorno = request.form.get("motivo_retorno")
        observacao = (request.form.get("observacao") or "").strip() or "N/D"
        assinatura_tecnico = request.form.get("assinatura_tecnico")
        assinatura_logistica = request.form.get("assinatura_logistica")

        item_ids = request.form.getlist("item_id[]")
        quantidades = request.form.getlist("quantidade[]")

        if tipo_transferencia not in ["saida", "retorno"]:
            flash("Tipo de transferência inválido.", "danger")
            return redirect(url_for("ferramentas_epis.transferencia"))

        if not tecnico_id:
            flash("Selecione o técnico.", "warning")
            return redirect(url_for("ferramentas_epis.transferencia"))

        if not item_ids or not quantidades:
            flash("Adicione pelo menos um item.", "warning")
            return redirect(url_for("ferramentas_epis.transferencia"))

        if tipo_transferencia == "retorno" and motivo_retorno not in MOTIVOS_RETORNO:
            flash("Selecione um motivo válido para o retorno.", "warning")
            return redirect(url_for("ferramentas_epis.transferencia"))

        try:
            if tipo_transferencia == "saida":
                status_geral = "tecnico"
                motivo_geral = "Saída Empresa → Técnico"
                local_geral = "TÉCNICO"
            else:
                mapa_status = {
                    "devolucao": "devolvido",
                    "troca": "troca",
                    "extravio": "extraviado",
                    "perda": "perdido",
                    "desgaste": "desgaste",
                    "mau_uso": "mau_uso"
                }

                mapa_motivo = {
                    "devolucao": "Devolução",
                    "troca": "Troca",
                    "extravio": "Extravio",
                    "perda": "Perda",
                    "desgaste": "Desgaste",
                    "mau_uso": "Mau uso"
                }

                status_geral = mapa_status[motivo_retorno]
                motivo_geral = mapa_motivo[motivo_retorno]
                local_geral = "EMPRESA" if motivo_retorno == "devolucao" else "BAIXA PATRIMONIAL"

            primeiro_item_id = item_ids[0] if item_ids else None

            historico = HistoricoEquipamento(
                item_id=primeiro_item_id,
                tecnico_id=tecnico_id,
                categoria="multiplo",
                tipo_movimentacao=tipo_transferencia,
                local=local_geral,
                status=status_geral,
                motivo=motivo_geral,
                observacao=observacao,
                assinatura_tecnico=assinatura_tecnico,
                assinatura_logistica=assinatura_logistica,
                email_enviado=False,
                data_hora=datetime.utcnow()
            )

            db.session.add(historico)
            db.session.flush()

            itens_processados = 0

            for item_id, qtd in zip(item_ids, quantidades):
                quantidade = int(qtd or 0)

                if not item_id or quantidade <= 0:
                    continue

                item = Item.query.get_or_404(item_id)
                categoria = normalizar_categoria(item.categoria)

                if categoria not in ["FERRAMENTA", "EPI"]:
                    db.session.rollback()
                    flash(f"O item {item.descricao} não é Ferramenta nem EPI.", "danger")
                    return redirect(url_for("ferramentas_epis.transferencia"))

                valor_unitario = item_valor(item)
                valor_total = valor_unitario * quantidade

                if tipo_transferencia == "saida":
                    if not debitar_estoque_empresa(item.id, quantidade):
                        db.session.rollback()
                        flash(f"Estoque insuficiente para {item.descricao}.", "danger")
                        return redirect(url_for("ferramentas_epis.transferencia"))

                    posse = EquipamentoTecnico(
                        item_id=item.id,
                        tecnico_id=tecnico_id,
                        categoria=categoria.lower(),
                        local="TÉCNICO",
                        status="tecnico",
                        quantidade=quantidade,
                        valor_unitario=valor_unitario,
                        valor_total=valor_total,
                        data_hora=datetime.utcnow()
                    )
                    db.session.add(posse)

                else:
                    ok = remover_posse_tecnico(
                        item_id=item.id,
                        tecnico_id=tecnico_id,
                        quantidade=quantidade,
                        novo_status=status_geral,
                        motivo=motivo_geral
                    )

                    if not ok:
                        db.session.rollback()
                        flash(f"O técnico não possui saldo suficiente do item {item.descricao}.", "danger")
                        return redirect(url_for("ferramentas_epis.transferencia"))

                    if motivo_retorno == "devolucao":
                        creditar_estoque_empresa(item.id, quantidade)

                historico_item = HistoricoEquipamentoItem(
                    historico_id=historico.id,
                    item_id=item.id,
                    quantidade=quantidade,
                    categoria=categoria.lower(),
                    valor_unitario=valor_unitario,
                    valor_total=valor_total
                )

                db.session.add(historico_item)
                itens_processados += 1

            if itens_processados == 0:
                db.session.rollback()
                flash("Nenhum item válido foi informado.", "warning")
                return redirect(url_for("ferramentas_epis.transferencia"))

            db.session.commit()
            
            # ==================================================
# GERAR TERMO PDF E ENVIAR E-MAIL AO TÉCNICO
# ==================================================
            try:
                with current_app.test_request_context():
                    gerar_termo(historico.id)

                from app.utils.mailer import send_termo_ferramenta_email

                historico = HistoricoEquipamento.query.get(historico.id)

                enviado = send_termo_ferramenta_email(historico)

                if enviado:
                    historico.email_enviado = True
                    db.session.commit()

            except Exception as e:
                current_app.logger.exception(
                    f"Erro ao gerar/enviar termo por e-mail: {e}"
                )

            if tipo_transferencia == "saida":
    
                if enviado:
                    flash(
                        f"Saída registrada com sucesso. Termo enviado para {historico.tecnico.email}.",
                        "success"
                    )
                else:
                    flash(
                        "Saída registrada com sucesso, porém o e-mail não foi enviado.",
                        "warning"
                    )

            else:

                if enviado:
                    flash(
                        f"Retorno registrado com sucesso. Termo enviado para {historico.tecnico.email}.",
                        "success"
                    )
                else:
                    flash(
                        "Retorno registrado com sucesso, porém o e-mail não foi enviado.",
                        "warning"
                )
            return redirect(url_for("ferramentas_epis.historico"))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao registrar transferência: {str(e)}", "danger")
            return redirect(url_for("ferramentas_epis.transferencia"))

    return render_template(
        "ferramentas_epis/transferencia.html",
        tecnicos=tecnicos,
        itens=itens,
        motivos_retorno=MOTIVOS_RETORNO
    )


# ==========================================================
# ROTAS ANTIGAS - REDIRECIONAMENTO SEGURO
# ==========================================================

@bp_ferramentas_epis.route("/nova-entrega")
@login_required
def nova_entrega():
    return redirect(url_for("ferramentas_epis.transferencia"))


@bp_ferramentas_epis.route("/devolucao")
@login_required
def devolucao():
    return redirect(url_for("ferramentas_epis.transferencia"))


@bp_ferramentas_epis.route("/ocorrencia")
@login_required
def ocorrencia():
    return redirect(url_for("ferramentas_epis.transferencia"))


# ==========================================================
# API - ITENS EM POSSE DO TÉCNICO
# ==========================================================

@bp_ferramentas_epis.route("/api/itens-tecnico/<int:tecnico_id>")
@login_required
def api_itens_tecnico(tecnico_id):
    saldos = (
        db.session.query(
            Item.id.label("item_id"),
            Item.codigo,
            Item.descricao,
            Item.categoria,
            func.sum(EquipamentoTecnico.quantidade).label("quantidade")
        )
        .join(Item, Item.id == EquipamentoTecnico.item_id)
        .filter(
            EquipamentoTecnico.tecnico_id == tecnico_id,
            EquipamentoTecnico.status == "tecnico"
        )
        .group_by(Item.id, Item.codigo, Item.descricao, Item.categoria)
        .order_by(Item.descricao.asc())
        .all()
    )

    return jsonify([
        {
            "item_id": s.item_id,
            "codigo": s.codigo,
            "descricao": s.descricao,
            "categoria": s.categoria,
            "quantidade": int(s.quantidade or 0)
        }
        for s in saldos
    ])


# ==========================================================
# API - ITENS DISPONÍVEIS NO ESTOQUE EMPRESA
# ==========================================================

@bp_ferramentas_epis.route("/api/itens-empresa")
@login_required
def api_itens_empresa():
    registros = (
        db.session.query(Estoque, Item)
        .join(Item, Item.id == Estoque.item_id)
        .filter(
            Estoque.quantidade > 0,
            Item.categoria.in_(["FERRAMENTA", "EPI", "ferramenta", "epi"])
        )
        .order_by(Item.descricao.asc())
        .all()
    )

    return jsonify([
        {
            "item_id": item.id,
            "codigo": item.codigo,
            "descricao": item.descricao,
            "categoria": item.categoria,
            "quantidade": int(estoque.quantidade or 0)
        }
        for estoque, item in registros
    ])


# ==========================================================
# SALDO POR TÉCNICO
# ==========================================================

@bp_ferramentas_epis.route("/saldo")
@login_required
def saldo_tecnico():
    tecnico_id = request.args.get("tecnico_id")
    categoria = request.args.get("categoria")

    query = (
        db.session.query(
            Tecnico.id.label("tecnico_id"),
            Tecnico.nome.label("tecnico_nome"),
            Item.id.label("item_id"),
            Item.codigo,
            Item.descricao,
            Item.categoria.label("categoria"),
            func.sum(EquipamentoTecnico.quantidade).label("quantidade"),
            func.max(EquipamentoTecnico.valor_unitario).label("valor_unitario"),
            func.sum(EquipamentoTecnico.valor_total).label("valor_total")
        )
        .join(Tecnico, Tecnico.id == EquipamentoTecnico.tecnico_id)
        .join(Item, Item.id == EquipamentoTecnico.item_id)
        .filter(EquipamentoTecnico.status == "tecnico")
    )

    if tecnico_id:
        query = query.filter(EquipamentoTecnico.tecnico_id == tecnico_id)

    if categoria:
        query = query.filter(
        func.lower(Item.categoria) == categoria.lower()
    )

    saldos = (
        query
        .group_by(
            Tecnico.id,
            Tecnico.nome,
            Item.id,
            Item.codigo,
            Item.descricao,
            Item.categoria
        )
        .order_by(
            Tecnico.nome.asc(),
            Item.categoria.asc(),
            Item.descricao.asc()
        )
        .all()
    )

    tecnicos = Tecnico.query.order_by(Tecnico.nome.asc()).all()

    return render_template(
        "ferramentas_epis/saldo_tecnico.html",
        saldos=saldos,
        tecnicos=tecnicos,
        tecnico_id=tecnico_id,
        categoria=categoria
    )
    
    
# ==========================================================
# EXPORTAR EXCEL - SALDO DE FERRAMENTAS & EPIs POR TÉCNICO
# ==========================================================

@bp_ferramentas_epis.route("/saldo/exportar")
@login_required
def exportar_saldo_tecnico():

    tecnico_id = request.args.get("tecnico_id")
    categoria = request.args.get("categoria")

    query = (
        db.session.query(
            Tecnico.nome.label("tecnico_nome"),
            Item.codigo,
            Item.descricao,
            Item.categoria.label("categoria"),
            func.sum(EquipamentoTecnico.quantidade).label("quantidade"),
            func.max(EquipamentoTecnico.valor_unitario).label("valor_unitario"),
            func.sum(EquipamentoTecnico.valor_total).label("valor_total")
        )
        .join(Tecnico, Tecnico.id == EquipamentoTecnico.tecnico_id)
        .join(Item, Item.id == EquipamentoTecnico.item_id)
        .filter(EquipamentoTecnico.status == "tecnico")
    )

    if tecnico_id:
        query = query.filter(EquipamentoTecnico.tecnico_id == tecnico_id)

    if categoria:
        query = query.filter(
            func.lower(Item.categoria) == categoria.lower()
        )

    saldos = (
        query
        .group_by(
            Tecnico.nome,
            Item.codigo,
            Item.descricao,
            Item.categoria
        )
        .order_by(
            Tecnico.nome.asc(),
            Item.categoria.asc(),
            Item.descricao.asc()
        )
        .all()
    )

    dados = []

    for saldo in saldos:
        quantidade = int(saldo.quantidade or 0)
        valor_unitario = float(saldo.valor_unitario or 0)
        valor_total = float(saldo.valor_total or 0)

        dados.append({
            "Técnico": saldo.tecnico_nome,
            "Código": saldo.codigo,
            "Descrição": saldo.descricao,
            "Categoria": (
                "EPI"
                if str(saldo.categoria).lower() == "epi"
                else "Ferramenta"
            ),
            "Quantidade": quantidade,
            "Valor Unitário": valor_unitario,
            "Valor Total": valor_total
        })

    df = pd.DataFrame(dados)

    if df.empty:
        df = pd.DataFrame(columns=[
            "Técnico",
            "Código",
            "Descrição",
            "Categoria",
            "Quantidade",
            "Valor Unitário",
            "Valor Total"
        ])

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

        df.to_excel(
            writer,
            sheet_name="Saldo Técnico",
            index=False,
            startrow=3
        )

        workbook = writer.book
        worksheet = writer.sheets["Saldo Técnico"]

        titulo_fmt = workbook.add_format({
            "bold": True,
            "font_size": 14,
            "font_color": "white",
            "bg_color": "#002b55",
            "align": "center",
            "valign": "vcenter",
            "border": 1
        })

        header_fmt = workbook.add_format({
            "bold": True,
            "font_color": "white",
            "bg_color": "#002b55",
            "border": 1,
            "align": "center"
        })

        money_fmt = workbook.add_format({
            "num_format": 'R$ #,##0.00',
            "border": 1
        })

        int_fmt = workbook.add_format({
            "num_format": "0",
            "border": 1,
            "align": "center"
        })

        text_fmt = workbook.add_format({
            "border": 1
        })

        worksheet.merge_range(
            "A1:G1",
            "SALDO DE FERRAMENTAS & EPIs POR TÉCNICO",
            titulo_fmt
        )

        for col_num, col_name in enumerate(df.columns):
            worksheet.write(3, col_num, col_name, header_fmt)

        for row_num in range(4, 4 + len(df)):
            worksheet.set_row(row_num, 18)

        worksheet.set_column("A:A", 28, text_fmt)
        worksheet.set_column("B:B", 16, text_fmt)
        worksheet.set_column("C:C", 40, text_fmt)
        worksheet.set_column("D:D", 18, text_fmt)
        worksheet.set_column("E:E", 14, int_fmt)
        worksheet.set_column("F:G", 18, money_fmt)

        worksheet.freeze_panes(4, 0)
        worksheet.autofilter(3, 0, 3, 6)

        total_row = 4 + len(df)

        worksheet.merge_range(total_row, 0, total_row, 3, "TOTAL GERAL", header_fmt)

        if len(df) > 0:
            worksheet.write_formula(
                total_row,
                4,
                f"=SUM(E5:E{total_row})",
                int_fmt
            )
            worksheet.write_blank(total_row, 5, None, money_fmt)
            worksheet.write_formula(
                total_row,
                6,
                f"=SUM(G5:G{total_row})",
                money_fmt
            )
        else:
            worksheet.write(total_row, 4, 0, int_fmt)
            worksheet.write_blank(total_row, 5, None, money_fmt)
            worksheet.write(total_row, 6, 0, money_fmt)

    output.seek(0)

    nome_arquivo = (
        "saldo_ferramentas_epis_tecnicos_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )

    return send_file(
        output,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


# ==========================================================
# HISTÓRICO COM FILTROS
# ==========================================================

@bp_ferramentas_epis.route("/historico")
@login_required
def historico():
    tecnico_id = request.args.get("tecnico_id")
    categoria = request.args.get("categoria")
    tipo_movimentacao = request.args.get("tipo_movimentacao")
    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    item_busca = request.args.get("item")

    query = (
        HistoricoEquipamento.query
        .outerjoin(Tecnico, Tecnico.id == HistoricoEquipamento.tecnico_id)
    )

    if tecnico_id:
        query = query.filter(HistoricoEquipamento.tecnico_id == tecnico_id)

    if categoria:
        query = query.filter(HistoricoEquipamento.categoria == categoria)

    if tipo_movimentacao:
        query = query.filter(HistoricoEquipamento.tipo_movimentacao == tipo_movimentacao)

    if status:
        query = query.filter(HistoricoEquipamento.status == status)

    if item_busca:
        query = (
            query
            .join(HistoricoEquipamentoItem, HistoricoEquipamentoItem.historico_id == HistoricoEquipamento.id)
            .join(Item, Item.id == HistoricoEquipamentoItem.item_id)
            .filter(
                or_(
                    Item.codigo.ilike(f"%{item_busca}%"),
                    Item.descricao.ilike(f"%{item_busca}%")
                )
            )
        )

    if data_inicio:
        query = query.filter(HistoricoEquipamento.data_hora >= data_inicio)

    if data_fim:
        query = query.filter(HistoricoEquipamento.data_hora <= f"{data_fim} 23:59:59")

    historico = (
        query
        .distinct()
        .order_by(HistoricoEquipamento.data_hora.desc())
        .all()
    )

    tecnicos = Tecnico.query.order_by(Tecnico.nome.asc()).all()

    return render_template(
        "ferramentas_epis/historico.html",
        historico=historico,
        tecnicos=tecnicos,
        filtros={
            "tecnico_id": tecnico_id,
            "categoria": categoria,
            "tipo_movimentacao": tipo_movimentacao,
            "status": status,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "item": item_busca
        }
    )
    
    
    # ==========================================================
# EXPORTAR RELATÓRIO GERENCIAL - FERRAMENTAS & EPIs
# ==========================================================

@bp_ferramentas_epis.route("/exportar-relatorio-gerencial")
@login_required
def exportar_relatorio_gerencial():

    tecnico_id = request.args.get("tecnico_id")
    tipo_movimentacao = request.args.get("tipo_movimentacao")
    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    item_busca = request.args.get("item")

    query = (
        db.session.query(
            HistoricoEquipamento,
            HistoricoEquipamentoItem,
            Item,
            Tecnico
        )
        .join(
            HistoricoEquipamentoItem,
            HistoricoEquipamentoItem.historico_id == HistoricoEquipamento.id
        )
        .join(
            Item,
            Item.id == HistoricoEquipamentoItem.item_id
        )
        .outerjoin(
            Tecnico,
            Tecnico.id == HistoricoEquipamento.tecnico_id
        )
    )

    if tecnico_id:
        query = query.filter(HistoricoEquipamento.tecnico_id == tecnico_id)

    if tipo_movimentacao:
        query = query.filter(HistoricoEquipamento.tipo_movimentacao == tipo_movimentacao)

    if status:
        query = query.filter(HistoricoEquipamento.status == status)

    if item_busca:
        query = query.filter(
            or_(
                Item.codigo.ilike(f"%{item_busca}%"),
                Item.descricao.ilike(f"%{item_busca}%")
            )
        )

    if data_inicio:
        query = query.filter(HistoricoEquipamento.data_hora >= data_inicio)

    if data_fim:
        query = query.filter(HistoricoEquipamento.data_hora <= f"{data_fim} 23:59:59")

    registros = (
        query
        .order_by(
            HistoricoEquipamento.data_hora.desc(),
            Tecnico.nome.asc(),
            Item.descricao.asc()
        )
        .all()
    )

    def nome_operacao(tipo):
        mapa = {
            "saida": "Entrega ao Técnico",
            "retorno": "Retorno / Ocorrência"
        }
        return mapa.get((tipo or "").lower(), tipo or "-")

    def situacao_gerencial(status_item):
        status_item = (status_item or "").lower()

        if status_item == "tecnico":
            return "Em posse do técnico"

        if status_item == "devolvido":
            return "Devolvido ao estoque"

        if status_item in ["perdido", "extraviado", "mau_uso", "mau uso"]:
            return "Descontado"

        if status_item == "troca":
            return "Troca"

        if status_item == "desgaste":
            return "Desgaste"

        return status_item.capitalize() if status_item else "-"

    def impacto_financeiro(status_item):
        status_item = (status_item or "").lower()

        if status_item in ["perdido", "extraviado", "mau_uso", "mau uso"]:
            return "Sim"

        return "Não"

    dados_analitico = []

    for historico, item_hist, item, tecnico in registros:

        quantidade = item_hist.quantidade or 0
        valor_unitario = item_hist.valor_unitario or 0
        valor_total = item_hist.valor_total or 0

        dados_analitico.append({
            "Data": historico.data_hora.strftime("%d/%m/%Y %H:%M") if historico.data_hora else "",
            "Técnico": tecnico.nome if tecnico else "-",
            "Matrícula": getattr(tecnico, "matricula", "") if tecnico else "",
            "Operação": nome_operacao(historico.tipo_movimentacao),
            "Ocorrência": historico.motivo or "-",
            "Situação Gerencial": situacao_gerencial(historico.status),
            "Desconto": impacto_financeiro(historico.status),
            "Código": item.codigo if item else "-",
            "Descrição": item.descricao if item else "-",
            "Categoria": item_hist.categoria or (item.categoria if item else "-"),
            "Quantidade": quantidade,
            "Valor Unitário": valor_unitario,
            "Valor Total": valor_total,
            "Observação": historico.observacao or "",
            "Documento": historico.id
        })

    df_analitico = pd.DataFrame(dados_analitico)

    if df_analitico.empty:
        df_analitico = pd.DataFrame(columns=[
            "Data",
            "Técnico",
            "Matrícula",
            "Operação",
            "Ocorrência",
            "Situação Gerencial",
            "Desconto",
            "Código",
            "Descrição",
            "Categoria",
            "Quantidade",
            "Valor Unitário",
            "Valor Total",
            "Observação",
            "Documento"
        ])

    df_tecnico = (
        df_analitico
        .groupby(["Técnico", "Operação", "Ocorrência", "Situação Gerencial"], as_index=False)
        .agg({
            "Quantidade": "sum",
            "Valor Total": "sum"
        })
    )

    df_item = (
        df_analitico
        .groupby(["Código", "Descrição", "Categoria", "Operação", "Ocorrência", "Situação Gerencial"], as_index=False)
        .agg({
            "Quantidade": "sum",
            "Valor Total": "sum"
        })
    )

    total_entregue = df_analitico.loc[
        df_analitico["Operação"] == "Entrega ao Técnico",
        "Quantidade"
    ].sum()

    total_devolvido = df_analitico.loc[
        df_analitico["Situação Gerencial"] == "Devolvido ao estoque",
        "Quantidade"
    ].sum()

    total_descontado = df_analitico.loc[
        df_analitico["Situação Gerencial"] == "Descontado",
        "Quantidade"
    ].sum()

    total_em_posse = df_analitico.loc[
        df_analitico["Situação Gerencial"] == "Em posse do técnico",
        "Quantidade"
    ].sum()

    df_indicadores = pd.DataFrame([
        {"Indicador": "Total entregue aos técnicos", "Quantidade": total_entregue},
        {"Indicador": "Total devolvido ao estoque", "Quantidade": total_devolvido},
        {"Indicador": "Total descontado", "Quantidade": total_descontado},
        {"Indicador": "Total em posse dos técnicos", "Quantidade": total_em_posse},
    ])

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

        df_analitico.to_excel(
            writer,
            sheet_name="Analítico Geral",
            index=False
        )

        df_tecnico.to_excel(
            writer,
            sheet_name="Resumo por Técnico",
            index=False
        )

        df_item.to_excel(
            writer,
            sheet_name="Resumo por Item",
            index=False
        )

        df_indicadores.to_excel(
            writer,
            sheet_name="Indicadores",
            index=False
        )

        workbook = writer.book

        formato_cabecalho = workbook.add_format({
            "bold": True,
            "font_color": "white",
            "bg_color": "#002b55",
            "border": 1
        })

        formato_moeda = workbook.add_format({
            "num_format": 'R$ #,##0.00'
        })

        formato_numero = workbook.add_format({
            "num_format": "0"
        })

        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]

            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, 0, 20)

            worksheet.set_row(0, 20)

            for col_num, value in enumerate(
                writer.sheets[sheet_name].table[0] if False else []
            ):
                pass

        for sheet_name, df in {
            "Analítico Geral": df_analitico,
            "Resumo por Técnico": df_tecnico,
            "Resumo por Item": df_item,
            "Indicadores": df_indicadores
        }.items():

            worksheet = writer.sheets[sheet_name]

            for col_num, col_name in enumerate(df.columns):
                worksheet.write(0, col_num, col_name, formato_cabecalho)

                largura = max(
                    len(str(col_name)) + 3,
                    min(
                        35,
                        max([len(str(x)) for x in df[col_name].astype(str).head(100)] + [len(str(col_name))]) + 3
                    )
                )

                worksheet.set_column(col_num, col_num, largura)

                if col_name in ["Valor Unitário", "Valor Total"]:
                    worksheet.set_column(col_num, col_num, 16, formato_moeda)

                if col_name == "Quantidade":
                    worksheet.set_column(col_num, col_num, 12, formato_numero)

    output.seek(0)

    nome_arquivo = f"relatorio_gerencial_ferramentas_epis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==========================================================
# DETALHES DA TRANSFERÊNCIA
# ==========================================================

@bp_ferramentas_epis.route("/detalhes/<int:id>")
@login_required
def detalhes(id):
    historico = HistoricoEquipamento.query.get_or_404(id)

    itens_historico = (
        HistoricoEquipamentoItem.query
        .join(Item, Item.id == HistoricoEquipamentoItem.item_id)
        .filter(HistoricoEquipamentoItem.historico_id == historico.id)
        .order_by(Item.descricao.asc())
        .all()
    )

    return render_template(
        "ferramentas_epis/detalhes.html",
        historico=historico,
        itens_historico=itens_historico
    )


# ==========================================================
# GERAR TERMO PDF
# ==========================================================

@bp_ferramentas_epis.route("/gerar-termo/<int:id>")
@login_required
def gerar_termo(id):

    historico = HistoricoEquipamento.query.get_or_404(id)

    itens_historico = (
        HistoricoEquipamentoItem.query
        .join(Item, Item.id == HistoricoEquipamentoItem.item_id)
        .filter(HistoricoEquipamentoItem.historico_id == historico.id)
        .order_by(Item.descricao.asc())
        .all()
    )

    pasta_termos = os.path.join(
        current_app.root_path,
        "static",
        "termos_ferramentas"
    )

    os.makedirs(pasta_termos, exist_ok=True)

    nome_arquivo = f"termo_ferramenta_epi_{historico.id}.pdf"

    caminho_completo = os.path.join(
        pasta_termos,
        nome_arquivo
    )

    caminho_relativo = f"termos_ferramentas/{nome_arquivo}"

    c = canvas.Canvas(caminho_completo, pagesize=A4)

    largura, altura = A4

    margem = 42
    y = altura - 45

    azul = colors.HexColor("#002b55")
    cinza = colors.HexColor("#6b7280")

    def dinheiro(valor):
        return (
            f"R$ {float(valor or 0):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
        
            # ==================================================
    # PADRÃO VISUAL
    # ==================================================

    preto = colors.HexColor("#111827")
    cinza_borda = colors.HexColor("#d1d5db")
    cinza_claro = colors.HexColor("#f8fafc")

    margem = 28
    y = altura - 45

    def texto_curto(valor, limite):
        valor = str(valor or "-")
        return valor if len(valor) <= limite else valor[:limite - 3] + "..."

    # ==================================================
    # CABEÇALHO
    # ==================================================

    logo_path = os.path.join(
        current_app.root_path,
        "static",
        "img",
        "start_logo.png"
    )

    if os.path.exists(logo_path):
        c.drawImage(
            logo_path,
            margem,
            y - 18,
            width=120,
            height=42,
            preserveAspectRatio=True,
            mask="auto"
        )

    status = (historico.status or "").lower()
    tipo = (historico.tipo_movimentacao or "").lower()

    eh_desconto = status in [
        "perdido",
        "extraviado",
        "dano",
        "danificado",
        "mau_uso"
    ]

    if tipo == "saida":
        titulo = "TERMO DE RESPONSABILIDADE"
    elif eh_desconto:
        titulo = "TERMO DE OCORRÊNCIA"
    elif status == "devolvido":
        titulo = "COMPROVANTE DE DEVOLUÇÃO"
    else:
        titulo = "DOCUMENTO DE MOVIMENTAÇÃO"

    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(azul)
    c.drawRightString(largura - margem, y + 6, titulo)

    y -= 32

    c.setStrokeColor(azul)
    c.setLineWidth(2)
    c.line(margem, y, largura - margem, y)

    y -= 24

    data_doc = (
        historico.data_hora.strftime("%d/%m/%Y %H:%M")
        if historico.data_hora else "-"
    )

    c.setFont("Helvetica", 8.5)
    c.setFillColor(cinza)
    c.drawRightString(
        largura - margem,
        y,
        f"Documento Nº {historico.id} | Emissão: {data_doc}"
    )

    y -= 26

    # ==================================================
    # TEXTO DO TERMO
    # ==================================================

    if tipo == "saida":
        texto = (
        "Declaro o recebimento dos materiais/equipamentos abaixo relacionados, "
        "assumindo total responsabilidade pela guarda, conservação, uso adequado "
        "e devolução dos itens pertencentes à empresa quando solicitado. "
        "Fico ciente de que, em caso de perda, extravio, dano decorrente de mau uso, "
        "avaria, uso indevido ou não devolução injustificada dos materiais/equipamentos "
        "recebidos, poderei ser responsabilizado pelo ressarcimento correspondente ao valor "
        "dos itens, conforme apuração interna e de acordo com as normas e procedimentos vigentes da empresa."
    )
    elif status == "devolvido":
        texto = (
            "Fica registrado o retorno dos materiais/equipamentos abaixo relacionados "
            "ao estoque da empresa."
        )
    elif eh_desconto:
        texto = (
        "Declaro estar ciente da ocorrência registrada referente ao(s) material(is) "
        "e/ou equipamento(s) abaixo relacionado(s), reconhecendo que os itens foram "
        "classificados como perda, extravio, dano ou mau uso. Estou ciente de que "
        "poderá haver desconto correspondente ao valor do item, conforme avaliação "
        "e procedimentos internos adotados pela empresa."
    )
    else:
        texto = "Documento referente à movimentação de materiais/equipamentos."

    from textwrap import wrap

    c.setFont("Helvetica", 10)
    c.setFillColor(preto)

    for linha in wrap(texto, width=115):
        c.drawString(margem, y, linha)
        y -= 14

    y -= 18

    # ==================================================
    # DADOS
    # ==================================================

    tecnico = historico.tecnico.nome if historico.tecnico else "-"

    status_legivel = {
        "tecnico": "Em posse do técnico",
        "devolvido": "Devolvido",
        "desgaste": "Desgaste",
        "perdido": "Perda",
        "extraviado": "Extravio",
        "troca": "Troca",
        "dano": "Dano"
    }.get(status, historico.status or "-")

    c.setFillColor(azul)
    c.roundRect(margem, y, largura - (margem * 2), 24, 4, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margem + 10, y + 8, "DADOS DA TRANSFERÊNCIA")

    y -= 32

    dados = [
        ("Técnico", tecnico, "Ocorrência", historico.motivo or status_legivel),
        ("Tipo", tipo.capitalize() or "-", "Observação", historico.observacao or "-"),
    ]

    for i, linha_dados in enumerate(dados):
        c.setFillColor(cinza_claro if i % 2 == 0 else colors.white)
        c.rect(margem, y - 7, largura - (margem * 2), 24, fill=1, stroke=0)

        c.setStrokeColor(cinza_borda)
        c.setLineWidth(0.4)
        c.rect(margem, y - 7, largura - (margem * 2), 24, fill=0, stroke=1)

        label1, valor1, label2, valor2 = linha_dados

        c.setFillColor(azul)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(margem + 8, y + 2, f"{label1}:")

        c.setFillColor(preto)
        c.setFont("Helvetica", 8.5)
        c.drawString(margem + 78, y + 2, texto_curto(valor1, 45))

        if label2:
            c.setFillColor(azul)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(margem + 335, y + 2, f"{label2}:")

            c.setFillColor(preto)
            c.setFont("Helvetica", 8.5)
            c.drawString(margem + 390, y + 2, texto_curto(valor2, 25))

        y -= 24

    y -= 16

    # ==================================================
    # TABELA
    # ==================================================

    c.setFillColor(azul)
    c.roundRect(margem, y, largura - (margem * 2), 24, 4, fill=1, stroke=0)

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.white)

    c.drawString(margem + 10, y + 8, "Código")
    c.drawString(margem + 82, y + 8, "Descrição")
    c.drawString(margem + 350, y + 8, "Categoria")
    c.drawCentredString(margem + 455, y + 8, "Qtd.")
    c.drawRightString(largura - margem - 12, y + 8, "Valor Total")

    y -= 26

    total_geral = 0
    linha_num = 0

    for item_hist in itens_historico:
        if y < 170:
            c.showPage()
            y = altura - 60

        item = item_hist.item

        codigo = item.codigo if item else "-"
        descricao = item.descricao if item else "-"
        categoria = item_hist.categoria or "-"
        qtd = item_hist.quantidade or 0
        valor_total = item_hist.valor_total or 0

        total_geral += valor_total

        categoria = "EPI" if categoria.lower() == "epi" else categoria.capitalize()

        c.setFillColor(cinza_claro if linha_num % 2 == 0 else colors.white)
        c.rect(margem, y - 8, largura - (margem * 2), 26, fill=1, stroke=0)

        c.setFillColor(preto)
        c.setFont("Helvetica", 8.5)

        c.drawString(margem + 10, y, texto_curto(codigo, 14))
        c.drawString(margem + 82, y, texto_curto(descricao, 72))
        c.drawString(margem + 350, y, categoria)
        c.drawCentredString(margem + 455, y, str(qtd))
        c.drawRightString(largura - margem - 12, y, dinheiro(valor_total))

        c.setStrokeColor(cinza_borda)
        c.line(margem, y - 12, largura - margem, y - 12)

        y -= 28
        linha_num += 1

    # ==================================================
    # TOTAL
    # ==================================================

    y -= 10

    c.setFillColor(azul)
    c.roundRect(largura - margem - 190, y - 8, 190, 30, 6, fill=1, stroke=0)

    c.setFont("Helvetica-Bold", 11.5)
    c.setFillColor(colors.white)
    c.drawCentredString(
        largura - margem - 95,
        y + 3,
        f"TOTAL: {dinheiro(total_geral)}"
    )

    y -= 120

    # ==================================================
    # ASSINATURAS
    # ==================================================

    assinatura_tecnico = getattr(historico, "assinatura_tecnico", None)
    assinatura_logistica = getattr(historico, "assinatura_logistica", None)

    box_largura = 250
    box_altura = 105

    x1 = margem
    x2 = largura - margem - box_largura

    c.setStrokeColor(cinza_borda)
    c.setLineWidth(0.6)

    c.roundRect(x1, y - 18, box_largura, box_altura, 6, fill=0, stroke=1)
    c.roundRect(x2, y - 18, box_largura, box_altura, 6, fill=0, stroke=1)

    try:
        import base64
        from io import BytesIO
        from reportlab.lib.utils import ImageReader

        if assinatura_tecnico:
            if "," in assinatura_tecnico:
                assinatura_tecnico = assinatura_tecnico.split(",", 1)[1]

            img_tecnico = ImageReader(BytesIO(base64.b64decode(assinatura_tecnico)))

            c.drawImage(
                img_tecnico,
                x1 + 50,
                y + 28,
                width=150,
                height=42,
                preserveAspectRatio=True,
                mask="auto"
            )
        else:
            c.setFillColor(preto)
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(
                x1 + (box_largura / 2),
                y + 45,
                "Assinatura física"
            )

        if assinatura_logistica:
            if "," in assinatura_logistica:
                assinatura_logistica = assinatura_logistica.split(",", 1)[1]

            img_logistica = ImageReader(BytesIO(base64.b64decode(assinatura_logistica)))

            c.drawImage(
                img_logistica,
                x2 + 50,
                y + 28,
                width=150,
                height=42,
                preserveAspectRatio=True,
                mask="auto"
            )
        else:
            c.setFillColor(preto)
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(
                x2 + (box_largura / 2),
                y + 45,
                "Assinatura física"
            )

    except Exception as e:
        print("Erro assinatura:", e)

    linha_y = y + 22

    c.setStrokeColor(cinza)
    c.setLineWidth(0.8)

    c.line(x1 + 25, linha_y, x1 + box_largura - 25, linha_y)
    c.line(x2 + 25, linha_y, x2 + box_largura - 25, linha_y)

    c.setFillColor(preto)
    c.setFont("Helvetica-Bold", 8.5)

    c.drawCentredString(
        x1 + (box_largura / 2),
        linha_y - 17,
        "Assinatura do Técnico"
    )

    c.drawCentredString(
        x2 + (box_largura / 2),
        linha_y - 17,
        "Assinatura Almoxarifado / Logística"
    )

    c.setFont("Helvetica", 7.5)
    c.setFillColor(cinza)

    c.drawCentredString(
        x1 + (box_largura / 2),
        linha_y - 29,
        str(tecnico)
    )

    c.drawCentredString(
        x2 + (box_largura / 2),
        linha_y - 29,
        "Responsável pela conferência"
    )

    # ==================================================
    # RODAPÉ
    # ==================================================

    c.setFillColor(cinza)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(
        largura / 2,
        32,
        "Documento gerado automaticamente pelo LogiStock."
    )

    c.save()

    historico.termo_pdf = caminho_relativo
    db.session.commit()

    return send_file(
        caminho_completo,
        as_attachment=False
    )
