import os

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    send_file
)

from flask_login import login_required
from werkzeug.utils import secure_filename

from app.extensions import db

from app.models import (
    Veiculo,
    Tecnico,
    VistoriaVeiculo,
    VistoriaVeiculoItem,
    VistoriaVeiculoFoto
)

from datetime import datetime

from app.routes.frota import gerar_pdf_frota


bp_frota_vistoria = Blueprint(
    "frota_vistoria",
    __name__,
    url_prefix="/frota/vistorias"
)


# ==================================================
# NOVA VISTORIA
# ==================================================
@bp_frota_vistoria.route("/nova", methods=["GET", "POST"])
@login_required
def nova_vistoria():

    veiculos = Veiculo.query.order_by(
        Veiculo.placa.asc()
    ).all()

    tecnicos = Tecnico.query.order_by(
        Tecnico.nome.asc()
    ).all()

    checklist_padrao = [
        "Lataria",
        "Para-choque dianteiro",
        "Para-choque traseiro",
        "Faróis",
        "Lanternas",
        "Retrovisores",
        "Pneus",
        "Estepe",
        "Macaco",
        "Triângulo",
        "Chave de roda",
        "Painel",
        "Vidros",
        "Documentação",
        "CRLV",
        "Combustível"
    ]

    if request.method == "POST":

        vistoria = VistoriaVeiculo(
            veiculo_id=request.form.get(
                "veiculo_id",
                type=int
            ),

            tecnico_id=request.form.get(
                "tecnico_id",
                type=int
            ),

            tipo_vistoria=request.form.get(
                "tipo_vistoria"
            ),

            responsavel=request.form.get(
                "responsavel"
            ),

            km_atual=request.form.get(
                "km_atual",
                type=int
            ),

            combustivel=request.form.get(
                "combustivel"
            ),

            local_vistoria=request.form.get(
                "local_vistoria"
            ),

            observacao_geral=request.form.get(
                "observacao_geral"
            ),

            data_hora=datetime.utcnow()
        )

        db.session.add(vistoria)
        db.session.flush()

        # ==================================================
        # SALVAR FOTOS DA VISTORIA
        # ==================================================
        fotos = request.files.getlist("fotos")

        pasta_fotos = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
            "frota",
            "vistorias"
        )

        os.makedirs(pasta_fotos, exist_ok=True)

        for index, foto in enumerate(fotos):

            if foto and foto.filename:

                nome_original = secure_filename(foto.filename)

                extensao = nome_original.rsplit(".", 1)[1].lower()

                nome_salvo = (
                    f"vistoria_{vistoria.id}_"
                    f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_"
                    f"{index + 1}.{extensao}"
                )

                caminho_completo = os.path.join(
                    pasta_fotos,
                    nome_salvo
                )

                foto.save(caminho_completo)

                caminho_relativo = (
                    f"uploads/frota/vistorias/{nome_salvo}"
                )

                descricao_foto = request.form.get(
                    f"descricao_foto_{index}",
                    ""
                ).strip()

                foto_vistoria = VistoriaVeiculoFoto(
                    vistoria_id=vistoria.id,
                    descricao=descricao_foto,
                    caminho_arquivo=caminho_relativo
                )

                db.session.add(foto_vistoria)

        for item_nome in checklist_padrao:

            status = request.form.get(
                f"status_{item_nome}"
            )

            observacao = request.form.get(
                f"obs_{item_nome}"
            )

            item = VistoriaVeiculoItem(
                vistoria_id=vistoria.id,
                item=item_nome,
                status=status or "conforme",
                observacao=observacao
            )

            db.session.add(item)

        db.session.commit()

        flash(
            "Vistoria registrada com sucesso.",
            "success"
        )

        return redirect(
            url_for(
                "frota_vistoria.detalhe_vistoria",
                vistoria_id=vistoria.id
            )
        )

    return render_template(
        "frota/vistorias/nova_vistoria.html",
        veiculos=veiculos,
        tecnicos=tecnicos,
        checklist=checklist_padrao
    )

# ==================================================
# DETALHE
# ==================================================
@bp_frota_vistoria.route("/<int:vistoria_id>")
@login_required
def detalhe_vistoria(vistoria_id):

    vistoria = VistoriaVeiculo.query.get_or_404(
        vistoria_id
    )

    return render_template(
        "frota/vistorias/detalhe_vistoria.html",
        vistoria=vistoria
    )


# ==================================================
# HISTÓRICO
# ==================================================
@bp_frota_vistoria.route("/historico")
@login_required
def historico_vistorias():

    veiculo_id = request.args.get("veiculo_id", type=int)
    tipo_vistoria = request.args.get("tipo_vistoria", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()

    query = VistoriaVeiculo.query

    if veiculo_id:
        query = query.filter(
            VistoriaVeiculo.veiculo_id == veiculo_id
        )

    if tipo_vistoria:
        query = query.filter(
            VistoriaVeiculo.tipo_vistoria == tipo_vistoria
        )

    if data_inicio:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            query = query.filter(VistoriaVeiculo.data_hora >= inicio)
        except ValueError:
            pass

    if data_fim:
        try:
            fim = datetime.strptime(data_fim, "%Y-%m-%d")
            fim = fim.replace(hour=23, minute=59, second=59)
            query = query.filter(VistoriaVeiculo.data_hora <= fim)
        except ValueError:
            pass

    vistorias = (
        query
        .order_by(VistoriaVeiculo.data_hora.desc())
        .all()
    )

    veiculos = Veiculo.query.order_by(Veiculo.placa.asc()).all()

    return render_template(
        "frota/vistorias/historico_vistorias.html",
        vistorias=vistorias,
        veiculos=veiculos,
        veiculo_id=veiculo_id,
        tipo_vistoria=tipo_vistoria,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    
       # ==================================================
# FORMULÁRIO IMPRESSO DE VISTORIA
# ==================================================
@bp_frota_vistoria.route("/formulario-impressao")
@login_required
def formulario_impressao():

    checklist_padrao = [
        "Lataria",
        "Para-choque dianteiro",
        "Para-choque traseiro",
        "Faróis",
        "Lanternas",
        "Retrovisores",
        "Pneus",
        "Estepe",
        "Macaco",
        "Triângulo",
        "Chave de roda",
        "Painel",
        "Vidros",
        "Documentação",
        "CRLV",
        "Combustível",
        "Quilometragem",
        "Limpeza interna",
        "Limpeza externa"
    ]

    return render_template(
        "frota/vistorias/formulario_vistoria_impressao.html",
        checklist=checklist_padrao
    )
    
# ==================================================
# PDF - HISTÓRICO DE VISTORIAS
# ==================================================
@bp_frota_vistoria.route("/historico/pdf")
@login_required
def pdf_historico_vistorias():

    vistorias = (
        VistoriaVeiculo.query
        .order_by(
            VistoriaVeiculo.data_hora.desc()
        )
        .all()
    )

    dados = []

    for vistoria in vistorias:

        dados.append([
            vistoria.data_hora.strftime("%d/%m/%Y %H:%M")
            if vistoria.data_hora else "-",

            vistoria.veiculo.placa
            if vistoria.veiculo else "-",

            f"{vistoria.veiculo.marca} {vistoria.veiculo.modelo}"
            if vistoria.veiculo else "-",

            vistoria.tipo_vistoria or "-",

            vistoria.responsavel or "-",

            str(vistoria.km_atual or "-"),

            vistoria.combustivel or "-",

            vistoria.local_vistoria or "-",

            vistoria.observacao_geral or "-"
        ])

    pdf = gerar_pdf_frota(
        "Histórico de Vistorias",
        [
            "Data",
            "Placa",
            "Veículo",
            "Tipo",
            "Responsável",
            "KM",
            "Combustível",
            "Local",
            "Observação"
        ],
        dados or [[
            "-", "-", "-", "-", "-", "-", "-", "-", "-"
        ]]
    )

    return send_file(
        pdf,
        as_attachment=True,
        download_name="historico_vistorias.pdf",
        mimetype="application/pdf"
    )
    
@bp_frota_vistoria.route("/<int:vistoria_id>/pdf")
@login_required
def pdf_detalhe_vistoria(vistoria_id):

    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
        Image
    )

    vistoria = VistoriaVeiculo.query.get_or_404(vistoria_id)

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    elementos = []

    elementos.append(
        Paragraph(
            "<b>RELATÓRIO DE VISTORIA DE VEÍCULO</b>",
            styles["Title"]
        )
    )

    elementos.append(Spacer(1, 12))

    dados_cabecalho = [
        ["Tipo", vistoria.tipo_vistoria or "-"],
        ["Veículo", f"{vistoria.veiculo.marca} {vistoria.veiculo.modelo}" if vistoria.veiculo else "-"],
        ["Placa", vistoria.veiculo.placa if vistoria.veiculo else "-"],
        ["Técnico", vistoria.tecnico.nome if vistoria.tecnico else "-"],
        ["KM", str(vistoria.km_atual or "-")],
        ["Combustível", vistoria.combustivel or "-"],
        ["Data", vistoria.data_hora.strftime("%d/%m/%Y %H:%M") if vistoria.data_hora else "-"],
        ["Local", vistoria.local_vistoria or "-"],
        ["Responsável", vistoria.responsavel or "-"],
        ["Observações", vistoria.observacao_geral or "-"]
    ]

    tabela_cabecalho = Table(dados_cabecalho, colWidths=[110, 390])

    tabela_cabecalho.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#002b55")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))

    elementos.append(tabela_cabecalho)
    elementos.append(Spacer(1, 18))

    elementos.append(
        Paragraph("<b>CHECKLIST DA VISTORIA</b>", styles["Heading2"])
    )

    dados_checklist = [["Item", "Status", "Observação"]]

    for item in vistoria.itens:
        dados_checklist.append([
            item.item or "-",
            item.status or "-",
            item.observacao or "-"
        ])

    tabela_checklist = Table(
        dados_checklist,
        colWidths=[170, 100, 230]
    )

    tabela_checklist.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#002b55")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elementos.append(tabela_checklist)

    if vistoria.fotos:
        elementos.append(Spacer(1, 18))
        elementos.append(
            Paragraph("<b>FOTOS DA VISTORIA</b>", styles["Heading2"])
        )

        for foto in vistoria.fotos:
            caminho_foto = os.path.join(
                current_app.root_path,
                "static",
                foto.caminho_arquivo
            )

            if os.path.exists(caminho_foto):
                elementos.append(Spacer(1, 10))

                elementos.append(
                    Paragraph(
                        f"<b>{foto.descricao or 'Foto da vistoria'}</b>",
                        styles["Normal"]
                    )
                )

                img = Image(caminho_foto)
                img._restrictSize(420, 260)
                elementos.append(img)

    doc.build(elementos)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"vistoria_{vistoria.id}.pdf",
        mimetype="application/pdf"
    )