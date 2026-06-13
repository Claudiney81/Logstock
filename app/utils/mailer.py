# app/utils/mailer.py

from io import BytesIO
import os

from flask import current_app
from flask_mail import Message

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

from app.extensions import mail
from app.models import Tecnico


def _build_requisition_pdf(requisicao) -> bytes:
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )

    styles = getSampleStyleSheet()
    elems = []

    azul = colors.HexColor("#002b55")
    cinza_claro = colors.HexColor("#f3f6f9")
    cinza_borda = colors.HexColor("#c9c9c9")
    texto = colors.HexColor("#1f2937")

    def moeda(valor):
        return (
            f"R$ {float(valor or 0):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    # ======================================================
    # CABEÇALHO COM LOGO
    # ======================================================

    logo_path = os.path.join(
        current_app.root_path,
        "static",
        "img",
        "start_logo.png"
    )

    logo = ""

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=3.0 * cm, height=1.4 * cm)

    titulo = Paragraph(
        f"""
        <para align="right">
            <font size="17" color="#002b55">
                <b>Requisição Comprovante</b>
            </font><br/>
            <font size="9" color="#374151">
                Requisição Nº {requisicao.id}
            </font>
        </para>
        """,
        styles["Normal"]
    )

    cabecalho = Table(
        [[logo, titulo]],
        colWidths=[6 * cm, 11.5 * cm]
    )

    cabecalho.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 2, azul),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    elems.append(cabecalho)
    elems.append(Spacer(1, 16))

    # ======================================================
    # DADOS DA REQUISIÇÃO
    # ======================================================

    status = (
        requisicao.status.replace("_", " ").capitalize()
        if requisicao.status
        else "-"
    )

    data_hora = (
        requisicao.data_hora.strftime("%d/%m/%Y %H:%M")
        if requisicao.data_hora
        else "-"
    )

    cliente_os = "-"

    if getattr(requisicao, "os_cliente", None):
        cliente_os = requisicao.os_cliente
    elif getattr(requisicao, "cliente", None):
        cliente_os = requisicao.cliente.razao_social

    dados = [
        ["Técnico:", requisicao.solicitante_tecnico or "-", "Status:", status],

        ["Data / Hora:", data_hora, "Tipo Serviço:",
        requisicao.tipo_servico or "-"],

        ["Tipo Estoque:",
        requisicao.tipo_estoque or "empresa",
        "Observação:",
        requisicao.observacao or "N/D"],
    ]

    titulo_dados = Table(
        [["DADOS DA ENTREGA"]],
        colWidths=[17.5 * cm]
    )

    titulo_dados.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), azul),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    elems.append(titulo_dados)

    tabela_dados = Table(
        dados,
        colWidths=[3 * cm, 5.7 * cm, 3 * cm, 5.8 * cm]
    )

    tabela_dados.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, cinza_borda),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, -1), texto),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), azul),
        ("TEXTCOLOR", (2, 0), (2, -1), azul),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    elems.append(tabela_dados)
    elems.append(Spacer(1, 18))

    # ======================================================
    # ITENS ENTREGUES
    # ======================================================

    data = [[
        "Código",
        "Descrição",
        "Un.",
        "Qtd.",
        "Valor Unit.",
        "Valor Total"
    ]]

    total_geral = 0

    for item in requisicao.itens:
        quantidade = int(item.quantidade or 0)
        valor_unit = float(getattr(item, "valor", 0) or 0)
        valor_total = quantidade * valor_unit
        total_geral += valor_total

        data.append([
            item.codigo or "-",
            Paragraph(item.descricao or "-", styles["Normal"]),
            getattr(item, "unidade", "") or "-",
            quantidade,
            moeda(valor_unit),
            moeda(valor_total),
        ])

    tabela_itens = Table(
        data,
        colWidths=[2.2 * cm, 8.3 * cm, 1.2 * cm, 1.2 * cm, 2.2 * cm, 2.4 * cm],
        repeatRows=1
    )

    tabela_itens.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), azul),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),

        ("GRID", (0, 0), (-1, -1), 0.5, cinza_borda),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),

        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (3, -1), "CENTER"),
        ("ALIGN", (4, 1), (5, -1), "RIGHT"),

        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
    ]))

    elems.append(tabela_itens)
    elems.append(Spacer(1, 16))

    # ======================================================
    # TOTAL
    # ======================================================

    tabela_total = Table(
        [[
            Paragraph(
                '<para align="right"><b>TOTAL GERAL:</b></para>',
                styles["Normal"]
            ),
            Paragraph(
                f'<para align="center"><font color="white" size="13"><b>{moeda(total_geral)}</b></font></para>',
                styles["Normal"]
            )
        ]],
        colWidths=[13.5 * cm, 4 * cm]
    )

    tabela_total.setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), azul),
        ("BOX", (0, 0), (-1, -1), 0.6, cinza_borda),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (0, 0), 12),
    ]))

    elems.append(tabela_total)
    elems.append(Spacer(1, 14))

    # ======================================================
    # ASSINATURA
    # ======================================================

    assinatura_img = None

    if getattr(requisicao, "assinatura_path", None):

        assinatura_abs = os.path.join(
            current_app.root_path,
            "static",
            requisicao.assinatura_path
        ).replace("\\", "/")

        if os.path.exists(assinatura_abs):
            assinatura_img = Image(
                assinatura_abs,
                width=6.2 * cm,
                height=2.2 * cm
            )

    if not assinatura_img and getattr(requisicao, "assinatura_base64", None):
        assinatura_base64 = requisicao.assinatura_base64
        if "," in assinatura_base64:
            assinatura_base64 = assinatura_base64.split(",", 1)[1]

        try:
            assinatura_bytes = base64.b64decode(assinatura_base64)
            assinatura_img = Image(
                BytesIO(assinatura_bytes),
                width=6.2 * cm,
                height=2.2 * cm
            )
        except Exception:
            assinatura_img = None

    titulo_ass = Table(
        [["ASSINATURA DO TÉCNICO"]],
        colWidths=[17.5 * cm]
    )

    titulo_ass.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), azul),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    elems.append(titulo_ass)
    elems.append(Spacer(1, 10))

    if assinatura_img:
        assinatura_img.hAlign = "CENTER"
        assinatura_conteudo = assinatura_img
    else:
        assinatura_conteudo = Paragraph(
            '<para align="center"><font size="12"><b>Assinatura física</b></font></para>',
            styles["Normal"]
        )

    linha = Table(
        [[
            assinatura_conteudo
        ], [
            Paragraph(
                f'<para align="center"><b>{requisicao.solicitante_tecnico or "Técnico"}</b><br/>Assinatura de recebimento</para>',
                styles["Normal"]
            )
        ]],
        colWidths=[17.5 * cm],
        rowHeights=[2.6 * cm, None]
    )

    linha.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#c9c9c9")),
        ("LINEABOVE", (0, 1), (-1, 1), 0.8, colors.HexColor("#374151")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))

    elems.append(linha)

    elems.append(Spacer(1, 14))

    elems.append(
        Paragraph(
            '<para align="center"><font size="8" color="#6b7280">'
            'Documento gerado automaticamente pelo LogiStock.'
            '</font></para>',
            styles["Normal"],
        )
    )

    doc.build(elems)

    pdf_bytes = buf.getvalue()
    buf.close()

    return pdf_bytes
# ==========================================================
# ENVIO DE E-MAIL - REQUISIÇÃO MOBILE
# ==========================================================

def send_requisition_email(requisicao, attach_pdf: bool = True) -> bool:
    try:
        tecnico_nome = (requisicao.solicitante_tecnico or "").strip()

        dest_email = None

        if tecnico_nome:
            tecnico = Tecnico.query.filter_by(nome=tecnico_nome).first()

            if tecnico and tecnico.email:
                dest_email = tecnico.email

        if not dest_email:
            dest_email = current_app.config.get("MAIL_USERNAME")

        assunto = (
            f"[LogiStock] Comprovante de Entrega de Material "
            f"#{requisicao.id}"
        )

        msg = Message(
            subject=assunto,
            recipients=[dest_email],
        )

        msg.body = (
            f"Olá, {tecnico_nome or 'Técnico'}.\n\n"
            f"Segue em anexo o comprovante de entrega de material "
            f"referente à requisição #{requisicao.id}.\n\n"
            "Documento gerado automaticamente pelo LogiStock."
        )

        msg.html = (
            f"<p>Olá, <b>{tecnico_nome or 'Técnico'}</b>.</p>"
            f"<p>Segue em anexo o comprovante de entrega de material "
            f"referente à requisição <b>#{requisicao.id}</b>.</p>"
            "<p><i>Documento gerado automaticamente pelo LogiStock.</i></p>"
        )

        cc_cfg = current_app.config.get("MAIL_CC_DEFAULT")

        if cc_cfg:
            msg.cc = [cc_cfg] if isinstance(cc_cfg, str) else list(cc_cfg)

        if attach_pdf:
            pdf_bytes = _build_requisition_pdf(requisicao)
            filename = f"comprovante_entrega_material_{requisicao.id}.pdf"

            msg.attach(
                filename,
                "application/pdf",
                pdf_bytes,
            )

        mail.send(msg)

        current_app.logger.info(
            "Email da requisição %s enviado para %s",
            requisicao.id,
            dest_email,
        )

        return True

    except Exception as e:
        current_app.logger.exception(
            "Falha ao enviar e-mail da requisição %s: %s",
            requisicao.id,
            e,
        )

        return False


# ==========================================================
# PDF - BAIXA TÉCNICA
# ==========================================================

def _build_baixa_pdf(
    baixa,
    situacao: str = "",
    motivo: str = "",
    aprovacoes=None
) -> bytes:

    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )

    styles = getSampleStyleSheet()
    elems = []

    azul = colors.HexColor("#002b55")
    cinza_claro = colors.HexColor("#f3f6f9")
    cinza_borda = colors.HexColor("#c9c9c9")
    texto = colors.HexColor("#1f2937")

    # ======================================================
    # CABEÇALHO
    # ======================================================

    logo_path = os.path.join(
        current_app.root_path,
        "static",
        "img",
        "start_logo.png"
    )

    logo = ""

    if os.path.exists(logo_path):
        logo = Image(
            logo_path,
            width=3.0 * cm,
            height=1.4 * cm
        )

    titulo = Paragraph(
        """
        <para align="right">
            <font size="17" color="#002b55">
                <b>RELATÓRIO DE MATERIAL APLICADO</b>
            </font><br/>
            <font size="8" color="#4b5563">
                Documento operacional de materiais aplicados
            </font>
        </para>
        """,
        styles["Normal"]
    )

    cabecalho = Table(
        [[logo, titulo]],
        colWidths=[6 * cm, 11.5 * cm]
    )

    cabecalho.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 2, azul),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    elems.append(cabecalho)
    elems.append(Spacer(1, 14))

    # ======================================================
    # DADOS
    # ======================================================

    tecnico_nome = (
        getattr(baixa.tecnico, "nome", "-")
        if hasattr(baixa, "tecnico")
        else "-"
    )

    tipo_nome = (
        getattr(baixa.tipo_servico, "nome", "-")
        if hasattr(baixa, "tipo_servico")
        else "-"
    )

    data_hora = (
        baixa.data_hora.strftime("%d/%m/%Y %H:%M")
        if getattr(baixa, "data_hora", None)
        else "-"
    )

    status = (
        baixa.status.replace("_", " ").capitalize()
        if baixa.status
        else "-"
    )

    dados = [
    [
        "Técnico:",
        tecnico_nome,
        "Responsável:",
        baixa.responsavel or "-"
    ],
    [
        "Cliente / O.S:",
        getattr(baixa, "os_cliente", None) or "-",
        "Data / Hora:",
        data_hora
    ],
    [
        "Tipo Serviço:",
        tipo_nome,
        "Status:",
        status
    ],
    [
        "Observação:",
        baixa.observacao or "N/D",
        "",
        ""
    ],
]

    titulo_dados = Table(
        [["DADOS DA APLICAÇÃO"]],
        colWidths=[17.5 * cm]
    )

    titulo_dados.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), azul),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    elems.append(titulo_dados)

    tabela_dados = Table(
        dados,
        colWidths=[3 * cm, 5.7 * cm, 3 * cm, 5.8 * cm]
    )

    tabela_dados.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, cinza_borda),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, -1), texto),

        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),

        ("TEXTCOLOR", (0, 0), (0, -1), azul),
        ("TEXTCOLOR", (2, 0), (2, -1), azul),

        ("FONTSIZE", (0, 0), (-1, -1), 8.5),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),

        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    elems.append(tabela_dados)
    elems.append(Spacer(1, 16))

    # ======================================================
    # ITENS
    # ======================================================

    data_tbl = [[
        "Código",
        "Descrição",
        "Un.",
        "Qtd.",
        "Origem"
    ]]

    if aprovacoes is not None:

        for item_baixa, quantidade in (aprovacoes or []):

            item = getattr(item_baixa, "item", None)

            data_tbl.append([
                getattr(item, "codigo", "") if item else "",
                Paragraph(
                    getattr(item, "descricao", "") if item else "",
                    styles["Normal"]
                ),
                getattr(item, "unidade", "") if item else "",
                int(quantidade or 0),
                getattr(item_baixa, "tipo_estoque", "empresa").capitalize(),
            ])

    else:

        from app.models import BaixaTecnicaItem

        itens = BaixaTecnicaItem.query.filter_by(
            baixa_tecnica_id=baixa.id
        ).all()

        for item_baixa in itens:

            item = getattr(item_baixa, "item", None)

            data_tbl.append([
                getattr(item, "codigo", "") if item else "",
                Paragraph(
                    getattr(item, "descricao", "") if item else "",
                    styles["Normal"]
                ),
                getattr(item, "unidade", "") if item else "",
                int(item_baixa.quantidade or 0),
                getattr(item_baixa, "tipo_estoque", "empresa").capitalize(),
            ])

    table = Table(
        data_tbl,
        colWidths=[
            2.0 * cm,   # Código
            9.4 * cm,   # Descrição
            1.2 * cm,   # Un.
            1.2 * cm,   # Qtd.
            3.7 * cm,   # Origem
        ],
        repeatRows=1
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), azul),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

        ("FONTSIZE", (0, 0), (-1, 0), 8),

        ("ALIGN", (0, 0), (-1, 0), "CENTER"),

        ("GRID", (0, 0), (-1, -1), 0.5, cinza_borda),

        ("FONTSIZE", (0, 1), (-1, -1), 7.5),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),

        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),

        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, cinza_claro]),
    ]))

    elems.append(table)
    elems.append(Spacer(1, 18))

    elems.append(
        Paragraph(
            '<para align="center">'
            '<font size="8" color="#6b7280">'
            'Documento gerado automaticamente pelo LogiStock.'
            '</font>'
            '</para>',
            styles["Normal"]
        )
    )

    doc.build(elems)

    pdf_bytes = buf.getvalue()
    buf.close()

    return pdf_bytes

# ==========================================================
# ENVIO DE E-MAIL - BAIXA TÉCNICA APROVADA
# ==========================================================

def send_baixa_aprovada_email(baixa, aprovacoes=None, attach_pdf: bool = True) -> bool:
    try:
        tecnico = getattr(baixa, "tecnico", None)

        dest_email = None

        if tecnico and getattr(tecnico, "email", None):
            dest_email = tecnico.email

        if not dest_email:
            dest_email = current_app.config.get("MAIL_USERNAME")

        tecnico_nome = getattr(tecnico, "nome", "Técnico") if tecnico else "Técnico"
        tipo_nome = getattr(baixa.tipo_servico, "nome", "") if hasattr(baixa, "tipo_servico") else ""
        data_hora = (
            baixa.data_hora.strftime("%d/%m/%Y %H:%M")
            if getattr(baixa, "data_hora", None)
            else ""
        )

        assunto = f"[LogiStock] Baixa Técnica #{baixa.id} CONFIRMADA"

        msg = Message(
            subject=assunto,
            recipients=[dest_email],
        )

        msg.body = (
            f"Olá, {tecnico_nome}.\n\n"
            f"Sua baixa técnica #{baixa.id} foi CONFIRMADA.\n"
            f"Tipo de Serviço: {tipo_nome}\n"
            f"Data/Hora: {data_hora or '-'}\n"
            f"Responsável: {baixa.responsavel or '-'}\n\n"
            "Documento gerado automaticamente pelo LogiStock."
        )

        msg.html = (
            f"<p>Olá, <b>{tecnico_nome}</b>.</p>"
            f"<p>Sua baixa técnica <b>#{baixa.id}</b> foi "
            "<span style='color:#070'><b>CONFIRMADA</b></span>.</p>"
            "<ul style='margin:0;padding-left:18px'>"
            f"<li><b>Tipo de Serviço:</b> {tipo_nome}</li>"
            f"<li><b>Data/Hora:</b> {data_hora or '-'}</li>"
            f"<li><b>Responsável:</b> {baixa.responsavel or '-'}</li>"
            "</ul>"
            "<p><i>Documento gerado automaticamente pelo LogiStock.</i></p>"
        )

        cc_cfg = current_app.config.get("MAIL_CC_DEFAULT")

        if cc_cfg:
            msg.cc = [cc_cfg] if isinstance(cc_cfg, str) else list(cc_cfg)

        if attach_pdf:
            pdf_bytes = _build_baixa_pdf(
                baixa,
                situacao="CONFIRMADA",
                aprovacoes=aprovacoes,
            )

            filename = f"comprovante_baixa_{baixa.id}_confirmada.pdf"

            msg.attach(
                filename,
                "application/pdf",
                pdf_bytes,
            )

        mail.send(msg)

        current_app.logger.info(
            "Email de aprovação da baixa %s enviado para %s",
            baixa.id,
            dest_email,
        )

        return True

    except Exception as e:
        current_app.logger.exception(
            "Falha ao enviar e-mail de aprovação da baixa %s: %s",
            baixa.id,
            e,
        )

        return False


# ==========================================================
# ENVIO DE E-MAIL - BAIXA TÉCNICA RECUSADA
# ==========================================================

def send_baixa_recusa_email(baixa, motivo: str = "", attach_pdf: bool = True) -> bool:
    try:
        tecnico = getattr(baixa, "tecnico", None)

        dest_email = None

        if tecnico and getattr(tecnico, "email", None):
            dest_email = tecnico.email

        if not dest_email:
            dest_email = current_app.config.get("MAIL_USERNAME")

        tecnico_nome = getattr(tecnico, "nome", "Técnico") if tecnico else "Técnico"

        assunto = f"[LogiStock] Baixa Técnica #{baixa.id} RECUSADA"

        msg = Message(
            subject=assunto,
            recipients=[dest_email],
        )

        msg.body = (
            f"Olá, {tecnico_nome}.\n\n"
            f"Sua baixa técnica #{baixa.id} foi RECUSADA.\n"
            f"Motivo: {motivo or '-'}\n\n"
            "Documento gerado automaticamente pelo LogiStock."
        )

        msg.html = (
            f"<p>Olá, <b>{tecnico_nome}</b>.</p>"
            f"<p>Sua baixa técnica <b>#{baixa.id}</b> foi "
            "<span style='color:#a00'><b>RECUSADA</b></span>.</p>"
            f"<p><b>Motivo:</b> {motivo or '-'}</p>"
            "<p><i>Documento gerado automaticamente pelo LogiStock.</i></p>"
        )

        cc_cfg = current_app.config.get("MAIL_CC_DEFAULT")

        if cc_cfg:
            msg.cc = [cc_cfg] if isinstance(cc_cfg, str) else list(cc_cfg)

        if attach_pdf:
            pdf_bytes = _build_baixa_pdf(
                baixa,
                situacao="RECUSADA",
                motivo=motivo,
            )

            filename = f"comprovante_baixa_{baixa.id}_recusada.pdf"

            msg.attach(
                filename,
                "application/pdf",
                pdf_bytes,
            )

        mail.send(msg)

        current_app.logger.info(
            "Email de recusa da baixa %s enviado para %s",
            baixa.id,
            dest_email,
        )

        return True

    except Exception as e:
        current_app.logger.exception(
            "Falha ao enviar e-mail de recusa da baixa %s: %s",
            baixa.id,
            e,
        )

        return False
    
# ==========================================================
# ENVIO DE E-MAIL - MOVIMENTAÇÃO DE ESTOQUE
# ==========================================================

def _build_movimentacao_pdf(movimentacao) -> bytes:
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )

    styles = getSampleStyleSheet()
    elems = []

    azul = colors.HexColor("#002b55")
    cinza = colors.HexColor("#c9c9c9")

    def moeda(valor):
        return (
            f"R$ {float(valor or 0):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    tecnico = None

    if movimentacao.destino_tipo == "tecnico":
        tecnico = Tecnico.query.get(movimentacao.destino_id)

    elif movimentacao.origem_tipo == "tecnico":
        tecnico = Tecnico.query.get(movimentacao.origem_id)

    tecnico_nome = tecnico.nome if tecnico else "Técnico"
    assinatura_eh_operador = (
        (movimentacao.assinado_por or "").lower()
        in ["logistica", "operador", "almoxarifado"]
    )
    assinatura_titulo = (
        "ASSINATURA DO OPERADOR / LOGÍSTICA"
        if assinatura_eh_operador
        else "ASSINATURA DO TÉCNICO"
    )
    assinatura_nome = (
        "Operador / Logística"
        if assinatura_eh_operador
        else tecnico_nome
    )
    assinatura_legenda = (
        "Assinatura de conferência"
        if assinatura_eh_operador
        else "Assinatura de recebimento"
    )

    logo_path = os.path.join(
        current_app.root_path,
        "static",
        "img",
        "start_logo.png"
    )

    logo = ""

    if os.path.exists(logo_path):
        logo = Image(
            logo_path,
            width=3.0 * cm,
            height=1.4 * cm
        )

    titulo = Paragraph(
        f"""
        <para align="right">
            <font size="17" color="#002b55">
                <b>Comprovante de Movimentação</b>
            </font><br/>
            <font size="9">
                Movimentação Nº {movimentacao.id}
            </font>
        </para>
        """,
        styles["Normal"]
    )

    cabecalho = Table(
        [[logo, titulo]],
        colWidths=[6 * cm, 11.5 * cm]
    )

    cabecalho.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 2, azul),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    elems.append(cabecalho)
    elems.append(Spacer(1, 16))

    data_hora = (
        movimentacao.data_hora.strftime("%d/%m/%Y %H:%M")
        if movimentacao.data_hora else "-"
    )

    dados = [
        ["Técnico:", tecnico_nome, "Data/Hora:", data_hora],
        ["Origem:", movimentacao.origem_tipo or "-", "Destino:", movimentacao.destino_tipo or "-"],
        ["Tipo Serviço:",
         movimentacao.tipo_servico.nome if movimentacao.tipo_servico else "-",
         "Observação:",
         movimentacao.observacao or "-"],
    ]

    titulo_dados = Table(
        [["DADOS DA MOVIMENTAÇÃO"]],
        colWidths=[17.5 * cm]
    )

    titulo_dados.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), azul),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    elems.append(titulo_dados)

    tabela_dados = Table(
        dados,
        colWidths=[3 * cm, 5.7 * cm, 3 * cm, 5.8 * cm]
    )

    tabela_dados.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, cinza),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    elems.append(tabela_dados)
    elems.append(Spacer(1, 18))

    data = [[
        "Código",
        "Descrição",
        "Un.",
        "Qtd.",
        "Valor Unit.",
        "Valor Total"
    ]]

    total_geral = 0

    for mov_item in movimentacao.itens:

        item = mov_item.item

        qtd = int(mov_item.quantidade or 0)
        valor = float(mov_item.valor_unitario or 0)
        total = qtd * valor

        total_geral += total

        data.append([
            item.codigo if item else "-",
            Paragraph(item.descricao if item else "-", styles["Normal"]),
            item.unidade if item else "-",
            qtd,
            moeda(valor),
            moeda(total),
        ])

    tabela_itens = Table(
        data,
        colWidths=[
            2.2 * cm,
            8.3 * cm,
            1.2 * cm,
            1.2 * cm,
            2.2 * cm,
            2.4 * cm
        ],
        repeatRows=1
    )

    tabela_itens.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), azul),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, cinza),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elems.append(tabela_itens)
    elems.append(Spacer(1, 14))

    total_tbl = Table(
        [[
            Paragraph(
                '<para align="right"><b>TOTAL GERAL:</b></para>',
                styles["Normal"]
            ),
            Paragraph(
                f'<para align="center"><font color="white"><b>{moeda(total_geral)}</b></font></para>',
                styles["Normal"]
            )
        ]],
        colWidths=[13.5 * cm, 4 * cm]
    )

    total_tbl.setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), azul),
        ("BOX", (0, 0), (-1, -1), 0.5, cinza),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    elems.append(total_tbl)
    elems.append(Spacer(1, 14))

    titulo_ass = Table(
        [[assinatura_titulo]],
        colWidths=[17.5 * cm]
    )

    titulo_ass.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), azul),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    elems.append(titulo_ass)
    elems.append(Spacer(1, 10))

    assinatura_renderizada = False

    if movimentacao.assinatura:

        try:
            import base64

            assinatura_data = movimentacao.assinatura

            if "," in assinatura_data:
                assinatura_data = assinatura_data.split(",", 1)[1]

            assinatura_bytes = base64.b64decode(
                assinatura_data
            )

            assinatura_img = Image(
                BytesIO(assinatura_bytes),
                width=6.2 * cm,
                height=2.2 * cm
            )

            assinatura_img.hAlign = "CENTER"

            assinatura_conteudo = assinatura_img
            assinatura_renderizada = True

        except Exception:
            pass

    if not assinatura_renderizada:
        assinatura_conteudo = Paragraph(
            '<para align="center"><font size="12"><b>Assinatura física</b></font></para>',
            styles["Normal"]
        )

    linha_nome = Table(
        [[assinatura_conteudo], [assinatura_nome]],
        colWidths=[17.5 * cm],
        rowHeights=[2.6 * cm, None]
    )

    linha_nome.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#c9c9c9")),
        ("LINEABOVE", (0, 1), (-1, 1), 0.8, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))

    elems.append(linha_nome)

    elems.append(
        Paragraph(
            f'<para align="center">{assinatura_legenda}</para>',
            styles["Normal"]
        )
    )

    elems.append(Spacer(1, 16))

    elems.append(
        Paragraph(
            '<para align="center"><font size="8" color="#6b7280">'
            'Documento gerado automaticamente pelo LogiStock.'
            '</font></para>',
            styles["Normal"]
        )
    )

    doc.build(elems)

    pdf_bytes = buf.getvalue()
    buf.close()

    return pdf_bytes


def send_movimentacao_email(movimentacao, attach_pdf=False):
    try:

        tecnico = None

        if movimentacao.destino_tipo == "tecnico":
            tecnico = Tecnico.query.get(
                movimentacao.destino_id
            )

        elif movimentacao.origem_tipo == "tecnico":
            tecnico = Tecnico.query.get(
                movimentacao.origem_id
            )

        if not tecnico:
            return False

        if not tecnico.email:
            return False

        assunto = (
            f"[LogiStock] Comprovante de Movimentação "
            f"#{movimentacao.id}"
        )

        msg = Message(
            subject=assunto,
            recipients=[tecnico.email]
        )

        msg.body = (
            f"Olá, {tecnico.nome}.\n\n"
            f"Sua movimentação #{movimentacao.id} foi registrada com sucesso.\n\n"
            "Documento gerado automaticamente pelo LogiStock."
        )

        msg.html = (
            f"<p>Olá, <b>{tecnico.nome}</b>.</p>"
            f"<p>Sua movimentação <b>#{movimentacao.id}</b> foi registrada com sucesso.</p>"
            "<p><i>Documento gerado automaticamente pelo LogiStock.</i></p>"
        )

        if attach_pdf:
            pdf_bytes = _build_movimentacao_pdf(
                movimentacao
            )

            msg.attach(
                f"comprovante_movimentacao_{movimentacao.id}.pdf",
                "application/pdf",
                pdf_bytes
            )

        mail.send(msg)

        return True

    except Exception as e:
        current_app.logger.exception(
            "Erro ao enviar e-mail movimentação: %s",
            e
        )

        return False
    
    # ==========================================================
# ENVIO DE E-MAIL - TERMO FERRAMENTAS / EPIs
# ==========================================================

def send_termo_ferramenta_email(historico) -> bool:
    try:
        tecnico = historico.tecnico

        if not tecnico or not tecnico.email:
            return False

        if not historico.termo_pdf:
            return False

        caminho_pdf = os.path.join(
            current_app.root_path,
            "static",
            historico.termo_pdf
        )

        if not os.path.exists(caminho_pdf):
            return False

        assunto = f"[LogiStock] Termo de Ferramentas / EPIs #{historico.id}"

        msg = Message(
            subject=assunto,
            recipients=[tecnico.email]
        )

        msg.body = (
            f"Olá, {tecnico.nome}.\n\n"
            f"Segue em anexo o termo referente à movimentação de Ferramentas / EPIs #{historico.id}.\n\n"
            "Documento gerado automaticamente pelo LogiStock."
        )

        msg.html = (
            f"<p>Olá, <b>{tecnico.nome}</b>.</p>"
            f"<p>Segue em anexo o termo referente à movimentação de "
            f"Ferramentas / EPIs <b>#{historico.id}</b>.</p>"
            "<p><i>Documento gerado automaticamente pelo LogiStock.</i></p>"
        )

        with open(caminho_pdf, "rb") as f:
            msg.attach(
                f"termo_ferramenta_epi_{historico.id}.pdf",
                "application/pdf",
                f.read()
            )

        mail.send(msg)

        return True

    except Exception as e:
        current_app.logger.exception(
            "Erro ao enviar termo de ferramentas por e-mail: %s",
            e
        )
        return False
