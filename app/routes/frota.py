import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

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

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from app import db
from app.models import (
    Veiculo,
    ManutencaoVeiculo,
    AbastecimentoVeiculo,
    DocumentoVeiculo
)


frota_bp = Blueprint(
    "frota",
    __name__,
    url_prefix="/frota"
)


# ==================================================
# FUNÇÕES AUXILIARES
# ==================================================

EXTENSOES_PERMITIDAS = {
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "webp"
}


def converter_decimal(valor):
    if not valor:
        return Decimal("0.00")

    try:
        valor = str(valor).replace(".", "").replace(",", ".")
        return Decimal(valor)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def converter_data(data_str):
    if not data_str:
        return None

    try:
        return datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def arquivo_permitido(nome_arquivo):
    return (
        "." in nome_arquivo
        and nome_arquivo.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS
    )


def pasta_upload_documentos():
    pasta = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
        "frota",
        "documentos"
    )

    os.makedirs(pasta, exist_ok=True)

    return pasta


# ==================================================
# CADASTRAR VEÍCULO
# ==================================================

@frota_bp.route("/cadastrar", methods=["GET", "POST"])
@login_required
def cadastrar_veiculo():

    if request.method == "POST":
        placa = request.form.get("placa", "").strip().upper()
        marca = request.form.get("marca", "").strip()
        modelo = request.form.get("modelo", "").strip()
        ano = request.form.get("ano", "").strip()
        cor = request.form.get("cor", "").strip()
        tipo = request.form.get("tipo", "").strip()
        quilometragem_atual = request.form.get(
            "quilometragem_atual",
            "0"
        ).strip()
        responsavel = request.form.get("responsavel", "").strip()
        status = request.form.get("status", "ativo").strip()
        observacao = request.form.get("observacao", "").strip() or "N/D"

        if not placa or not marca or not modelo:
            flash("Placa, marca e modelo são obrigatórios.", "warning")
            return redirect(url_for("frota.cadastrar_veiculo"))

        veiculo_existente = Veiculo.query.filter_by(
            placa=placa
        ).first()

        if veiculo_existente:
            flash("Já existe um veículo cadastrado com esta placa.", "warning")
            return redirect(url_for("frota.cadastrar_veiculo"))

        try:
            ano = int(ano) if ano else None
        except ValueError:
            ano = None

        try:
            quilometragem_atual = (
                int(quilometragem_atual)
                if quilometragem_atual
                else 0
            )
        except ValueError:
            quilometragem_atual = 0

        novo_veiculo = Veiculo(
            placa=placa,
            marca=marca,
            modelo=modelo,
            ano=ano,
            cor=cor,
            tipo=tipo,
            quilometragem_atual=quilometragem_atual,
            responsavel=responsavel,
            status=status,
            observacao=observacao
        )

        db.session.add(novo_veiculo)
        db.session.commit()

        flash("Veículo cadastrado com sucesso.", "success")
        return redirect(url_for("frota.listar_veiculos"))

    return render_template("frota/cadastrar_veiculo.html")


# ==================================================
# LISTAR VEÍCULOS
# ==================================================

@frota_bp.route("/veiculos")
@login_required
def listar_veiculos():

    status = request.args.get("status", "")
    busca = request.args.get("busca", "").strip()

    query = Veiculo.query

    if status:
        query = query.filter(Veiculo.status == status)

    if busca:
        termo = f"%{busca}%"
        query = query.filter(
            db.or_(
                Veiculo.placa.ilike(termo),
                Veiculo.marca.ilike(termo),
                Veiculo.modelo.ilike(termo),
                Veiculo.responsavel.ilike(termo)
            )
        )

    veiculos = query.order_by(Veiculo.placa.asc()).all()

    return render_template(
        "frota/listar_veiculos.html",
        veiculos=veiculos,
        status=status,
        busca=busca
    )


# ==================================================
# EDITAR VEÍCULO
# ==================================================

@frota_bp.route("/editar/<int:veiculo_id>", methods=["GET", "POST"])
@login_required
def editar_veiculo(veiculo_id):

    veiculo = Veiculo.query.get_or_404(veiculo_id)

    if request.method == "POST":
        placa = request.form.get("placa", "").strip().upper()

        if not placa:
            flash("A placa é obrigatória.", "warning")
            return redirect(
                url_for(
                    "frota.editar_veiculo",
                    veiculo_id=veiculo.id
                )
            )

        placa_existente = (
            Veiculo.query
            .filter(
                Veiculo.placa == placa,
                Veiculo.id != veiculo.id
            )
            .first()
        )

        if placa_existente:
            flash("Já existe outro veículo com esta placa.", "warning")
            return redirect(
                url_for(
                    "frota.editar_veiculo",
                    veiculo_id=veiculo.id
                )
            )

        veiculo.placa = placa
        veiculo.marca = request.form.get("marca", "").strip()
        veiculo.modelo = request.form.get("modelo", "").strip()
        veiculo.cor = request.form.get("cor", "").strip()
        veiculo.tipo = request.form.get("tipo", "").strip()
        veiculo.responsavel = request.form.get("responsavel", "").strip()
        veiculo.status = request.form.get("status", "ativo").strip()
        veiculo.observacao = request.form.get("observacao", "").strip() or "N/D"

        try:
            veiculo.ano = (
                int(request.form.get("ano"))
                if request.form.get("ano")
                else None
            )
        except ValueError:
            veiculo.ano = None

        try:
            veiculo.quilometragem_atual = int(
                request.form.get("quilometragem_atual") or 0
            )
        except ValueError:
            veiculo.quilometragem_atual = 0

        db.session.commit()

        flash("Veículo atualizado com sucesso.", "success")
        return redirect(url_for("frota.listar_veiculos"))

    return render_template(
        "frota/editar_veiculo.html",
        veiculo=veiculo
    )


# ==================================================
# EXCLUIR VEÍCULO
# ==================================================

@frota_bp.route("/excluir/<int:veiculo_id>", methods=["POST"])
@login_required
def excluir_veiculo(veiculo_id):

    veiculo = Veiculo.query.get_or_404(veiculo_id)

    db.session.delete(veiculo)
    db.session.commit()

    flash("Veículo excluído com sucesso.", "success")
    return redirect(url_for("frota.listar_veiculos"))


# ==================================================
# NOVA MANUTENÇÃO
# ==================================================

@frota_bp.route("/manutencao/nova", methods=["GET", "POST"])
@login_required
def nova_manutencao():

    veiculos = Veiculo.query.order_by(Veiculo.placa.asc()).all()

    if request.method == "POST":
        veiculo_id = request.form.get("veiculo_id", type=int)
        tipo_manutencao = request.form.get(
            "tipo_manutencao",
            ""
        ).strip()
        data_manutencao = converter_data(
            request.form.get("data_manutencao")
        )
        quilometragem = request.form.get("quilometragem", "").strip()
        valor = converter_decimal(request.form.get("valor"))
        oficina = request.form.get("oficina", "").strip()
        responsavel = request.form.get("responsavel", "").strip()
        observacao = request.form.get("observacao", "").strip() or "N/D"

        if not veiculo_id or not tipo_manutencao or not data_manutencao:
            flash(
                "Veículo, tipo de manutenção e data são obrigatórios.",
                "warning"
            )
            return redirect(url_for("frota.nova_manutencao"))

        try:
            quilometragem = int(quilometragem) if quilometragem else None
        except ValueError:
            quilometragem = None

        manutencao = ManutencaoVeiculo(
            veiculo_id=veiculo_id,
            tipo_manutencao=tipo_manutencao,
            data_manutencao=data_manutencao,
            quilometragem=quilometragem,
            valor=valor,
            oficina=oficina,
            responsavel=responsavel,
            observacao=observacao
        )

        veiculo = Veiculo.query.get(veiculo_id)

        if veiculo and quilometragem:
            if quilometragem > (veiculo.quilometragem_atual or 0):
                veiculo.quilometragem_atual = quilometragem

            veiculo.status = "em manutencao"

        db.session.add(manutencao)
        db.session.commit()

        flash("Manutenção registrada com sucesso.", "success")
        return redirect(url_for("frota.historico_manutencao"))

    return render_template(
        "frota/nova_manutencao.html",
        veiculos=veiculos
    )


# ==================================================
# HISTÓRICO DE MANUTENÇÕES
# ==================================================

@frota_bp.route("/manutencoes", endpoint="historico_manutencao")
@login_required
def historico_manutencao():

        veiculo_id = request.args.get("veiculo_id", type=int)
        tipo_manutencao = request.args.get(
            "tipo_manutencao",
            ""
        ).strip()
        data_inicio = converter_data(request.args.get("data_inicio"))
        data_fim = converter_data(request.args.get("data_fim"))

        query = ManutencaoVeiculo.query.join(Veiculo)

        if veiculo_id:
            query = query.filter(
                ManutencaoVeiculo.veiculo_id == veiculo_id
            )

        if tipo_manutencao:
            query = query.filter(
                ManutencaoVeiculo.tipo_manutencao.ilike(
                    f"%{tipo_manutencao}%"
                )
            )

        if data_inicio:
            query = query.filter(
                ManutencaoVeiculo.data_manutencao >= data_inicio
            )

        if data_fim:
            query = query.filter(
                ManutencaoVeiculo.data_manutencao <= data_fim
            )

        manutencoes = query.order_by(
            ManutencaoVeiculo.data_manutencao.desc(),
            ManutencaoVeiculo.id.desc()
        ).all()

        veiculos = Veiculo.query.order_by(Veiculo.placa.asc()).all()

        return render_template(
            "frota/historico_manutencao.html",
            manutencoes=manutencoes,
            veiculos=veiculos,
            veiculo_id=veiculo_id,
            tipo_manutencao=tipo_manutencao,
            data_inicio=request.args.get("data_inicio", ""),
            data_fim=request.args.get("data_fim", "")
        )


# ==================================================
# NOVO ABASTECIMENTO
# ==================================================

@frota_bp.route("/abastecimento/novo", methods=["GET", "POST"])
@login_required
def novo_abastecimento():

    veiculos = Veiculo.query.order_by(Veiculo.placa.asc()).all()

    if request.method == "POST":
        veiculo_id = request.form.get("veiculo_id", type=int)
        data_abastecimento = converter_data(
            request.form.get("data_abastecimento")
        )
        quilometragem = request.form.get("quilometragem", "").strip()
        litros = converter_decimal(request.form.get("litros"))
        valor_total = converter_decimal(request.form.get("valor_total"))
        posto = request.form.get("posto", "").strip()
        responsavel = request.form.get("responsavel", "").strip()
        observacao = request.form.get("observacao", "").strip() or "N/D"

        if not veiculo_id or not data_abastecimento:
            flash(
                "Veículo e data do abastecimento são obrigatórios.",
                "warning"
            )
            return redirect(url_for("frota.novo_abastecimento"))

        try:
            quilometragem = int(quilometragem) if quilometragem else None
        except ValueError:
            quilometragem = None

        abastecimento = AbastecimentoVeiculo(
            veiculo_id=veiculo_id,
            data_abastecimento=data_abastecimento,
            quilometragem=quilometragem,
            litros=litros,
            valor_total=valor_total,
            posto=posto,
            responsavel=responsavel,
            observacao=observacao
        )

        veiculo = Veiculo.query.get(veiculo_id)

        if veiculo and quilometragem:
            if quilometragem > (veiculo.quilometragem_atual or 0):
                veiculo.quilometragem_atual = quilometragem

        db.session.add(abastecimento)
        db.session.commit()

        flash("Abastecimento registrado com sucesso.", "success")
        return redirect(url_for("frota.historico_abastecimento"))

    return render_template(
        "frota/novo_abastecimento.html",
        veiculos=veiculos
    )


# ==================================================
# HISTÓRICO DE ABASTECIMENTOS
# ==================================================

@frota_bp.route("/abastecimentos")
@login_required
def historico_abastecimento():

    veiculo_id = request.args.get("veiculo_id", type=int)
    data_inicio = converter_data(request.args.get("data_inicio"))
    data_fim = converter_data(request.args.get("data_fim"))

    query = AbastecimentoVeiculo.query.join(Veiculo)

    if veiculo_id:
        query = query.filter(
            AbastecimentoVeiculo.veiculo_id == veiculo_id
        )

    if data_inicio:
        query = query.filter(
            AbastecimentoVeiculo.data_abastecimento >= data_inicio
        )

    if data_fim:
        query = query.filter(
            AbastecimentoVeiculo.data_abastecimento <= data_fim
        )

    abastecimentos = query.order_by(
        AbastecimentoVeiculo.data_abastecimento.desc(),
        AbastecimentoVeiculo.id.desc()
    ).all()

    veiculos = Veiculo.query.order_by(Veiculo.placa.asc()).all()

    return render_template(
        "frota/historico_abastecimento.html",
        abastecimentos=abastecimentos,
        veiculos=veiculos,
        veiculo_id=veiculo_id,
        data_inicio=request.args.get("data_inicio", ""),
        data_fim=request.args.get("data_fim", "")
    )


# ==================================================
# NOVO DOCUMENTO DA FROTA
# ==================================================

@frota_bp.route("/documentos/novo", methods=["GET", "POST"])
@login_required
def novo_documento():

    veiculos = Veiculo.query.order_by(Veiculo.placa.asc()).all()

    if request.method == "POST":
        veiculo_id = request.form.get("veiculo_id", type=int)

        tipo_documento = request.form.get(
            "tipo_documento",
            ""
        ).strip()

        descricao = request.form.get("descricao", "").strip()
        data_emissao = converter_data(request.form.get("data_emissao"))
        data_validade = converter_data(request.form.get("data_validade"))
        observacao = request.form.get("observacao", "").strip() or "N/D"

        arquivos = request.files.getlist("arquivos")

        arquivos_validos = [
            arquivo for arquivo in arquivos
            if arquivo and arquivo.filename
        ]

        if not veiculo_id or not tipo_documento or not arquivos_validos:
            flash(
                "Veículo, tipo de documento e ao menos um arquivo são obrigatórios.",
                "warning"
            )
            return redirect(url_for("frota.novo_documento"))

        veiculo = Veiculo.query.get_or_404(veiculo_id)

        pasta = pasta_upload_documentos()

        total_salvos = 0

        for arquivo in arquivos_validos:

            if not arquivo_permitido(arquivo.filename):
                flash(
                    f"Formato inválido no arquivo: {arquivo.filename}. "
                    "Envie PDF, JPG, JPEG, PNG ou WEBP.",
                    "danger"
                )
                return redirect(url_for("frota.novo_documento"))

            nome_original = secure_filename(arquivo.filename)

            extensao = nome_original.rsplit(".", 1)[1].lower()

            placa_limpa = (
                veiculo.placa
                .replace("-", "")
                .replace(" ", "")
                .lower()
            )

            tipo_limpo = (
                tipo_documento
                .replace("/", "_")
                .replace(" ", "_")
                .lower()
            )

            nome_arquivo_salvo = (
                f"{placa_limpa}_{tipo_limpo}_"
                f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_"
                f"{total_salvos + 1}.{extensao}"
            )

            caminho_completo = os.path.join(
                pasta,
                nome_arquivo_salvo
            )

            arquivo.save(caminho_completo)

            caminho_relativo = (
                f"uploads/frota/documentos/{nome_arquivo_salvo}"
            )

            documento = DocumentoVeiculo(
                veiculo_id=veiculo_id,
                tipo_documento=tipo_documento,
                descricao=descricao,
                nome_arquivo=nome_original,
                caminho_arquivo=caminho_relativo,
                data_emissao=data_emissao,
                data_validade=data_validade,
                observacao=observacao
            )

            db.session.add(documento)
            total_salvos += 1

        db.session.commit()

        flash(
            f"{total_salvos} documento(s) enviado(s) com sucesso.",
            "success"
        )

        return redirect(url_for("frota.historico_documentos"))

    return render_template(
        "frota/novo_documento.html",
        veiculos=veiculos
    )


# ==================================================
# HISTÓRICO DE DOCUMENTOS DA FROTA
# ==================================================

@frota_bp.route("/documentos")
@login_required
def historico_documentos():

    veiculo_id = request.args.get("veiculo_id", type=int)
    tipo_documento = request.args.get(
        "tipo_documento",
        ""
    ).strip()

    query = DocumentoVeiculo.query.join(Veiculo)

    if veiculo_id:
        query = query.filter(
            DocumentoVeiculo.veiculo_id == veiculo_id
        )

    if tipo_documento:
        query = query.filter(
            DocumentoVeiculo.tipo_documento == tipo_documento
        )

    documentos = query.order_by(
        DocumentoVeiculo.data_upload.desc(),
        DocumentoVeiculo.id.desc()
    ).all()

    veiculos = Veiculo.query.order_by(Veiculo.placa.asc()).all()

    return render_template(
        "frota/historico_documentos.html",
        documentos=documentos,
        veiculos=veiculos,
        veiculo_id=veiculo_id,
        tipo_documento=tipo_documento
    )


# ==================================================
# EXCLUIR DOCUMENTO DA FROTA
# ==================================================

@frota_bp.route(
    "/documentos/excluir/<int:documento_id>",
    methods=["POST"]
)
@login_required
def excluir_documento(documento_id):

    documento = DocumentoVeiculo.query.get_or_404(documento_id)

    caminho_fisico = os.path.join(
        current_app.root_path,
        "static",
        documento.caminho_arquivo
    )

    if os.path.exists(caminho_fisico):
        os.remove(caminho_fisico)

    db.session.delete(documento)
    db.session.commit()

    flash("Documento excluído com sucesso.", "success")
    return redirect(url_for("frota.historico_documentos"))

# ==================================================
# GERADOR PDF PADRÃO
# ==================================================

def gerar_pdf_frota(titulo, colunas, dados):
    
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import Image
    from reportlab.lib.styles import ParagraphStyle

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm
    )

    elementos = []
    styles = getSampleStyleSheet()

    azul = colors.HexColor("#002b55")
    cinza_claro = colors.HexColor("#f3f6fa")
    cinza_borda = colors.HexColor("#cbd5e1")

    estilo_titulo = ParagraphStyle(
        "TituloFrota",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=azul,
        alignment=TA_CENTER,
        spaceAfter=6
    )

    estilo_subtitulo = ParagraphStyle(
        "SubtituloFrota",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#555555"),
        alignment=TA_CENTER
    )

    estilo_celula = ParagraphStyle(
        "CelulaFrota",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        alignment=TA_CENTER
    )

    estilo_obs = ParagraphStyle(
        "ObsFrota",
        parent=styles["Normal"],
        fontSize=8,
        leading=10
    )

    caminho_logo = os.path.join(
        current_app.root_path,
        "static",
        "img",
        "start_logo.png"
    )

    if os.path.exists(caminho_logo):
        logo = Image(caminho_logo, width=3.4 * cm, height=1.5 * cm)
    else:
        logo = Paragraph("<b>START</b>", styles["Normal"])

    data_emissao = datetime.now().strftime("%d/%m/%Y %H:%M")

    cabecalho = Table(
        [[
            logo,
            Paragraph(f"<b>{titulo}</b>", estilo_titulo),
            Paragraph(
                f"<para align='right'><b>Emissão:</b><br/>{data_emissao}</para>",
                styles["Normal"]
            )
        ]],
        colWidths=[4.0 * cm, 17.0 * cm, 5.2 * cm]
    )

    cabecalho.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, azul),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    elementos.append(cabecalho)
    elementos.append(Spacer(1, 8))

    elementos.append(
        Paragraph(
            "Relatório gerado automaticamente pelo sistema LogiStock.",
            estilo_subtitulo
        )
    )

    elementos.append(Spacer(1, 12))

    tabela_dados = [colunas]

    for linha in dados:
        nova_linha = []

        for index, valor in enumerate(linha):
            valor = "" if valor is None else str(valor)

            if index == len(linha) - 1:
                nova_linha.append(Paragraph(valor, estilo_obs))
            else:
                nova_linha.append(Paragraph(valor, estilo_celula))

        tabela_dados.append(nova_linha)

    if len(colunas) == 9:
        col_widths = [
            2.1 * cm,
            3.1 * cm,
            2.0 * cm,
            2.7 * cm,
            1.8 * cm,
            2.0 * cm,
            2.8 * cm,
            3.2 * cm,
            6.5 * cm
        ]
    else:
        largura_total = 26.2 * cm
        col_widths = [largura_total / len(colunas)] * len(colunas)

    tabela = Table(
        tabela_dados,
        colWidths=col_widths,
        repeatRows=1
    )

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), azul),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.45, cinza_borda),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
    ]))

    elementos.append(tabela)
    elementos.append(Spacer(1, 14))

    total_registros = len(dados)

    resumo = Table(
        [[
            Paragraph(
                f"<b>Total de registros:</b> {total_registros}",
                styles["Normal"]
            )
        ]],
        colWidths=[26.2 * cm]
    )

    resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cinza_claro),
        ("BOX", (0, 0), (-1, -1), 0.5, cinza_borda),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    elementos.append(resumo)

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#555555"))

        canvas.drawString(
            1.2 * cm,
            0.7 * cm,
            "START Energia e Inovação • LogiStock • Controle de Frota"
        )

        canvas.drawRightString(
            28.5 * cm,
            0.7 * cm,
            f"Página {doc.page}"
        )

        canvas.restoreState()

    doc.build(
        elementos,
        onFirstPage=rodape,
        onLaterPages=rodape
    )

    buffer.seek(0)

    return buffer

# ==================================================
# PDF - HISTÓRICO DE MANUTENÇÕES
# ==================================================

@frota_bp.route("/manutencoes/pdf")
@login_required
def pdf_manutencoes():

    veiculo_id = request.args.get("veiculo_id", type=int)
    tipo_manutencao = request.args.get("tipo_manutencao", "").strip()
    data_inicio = converter_data(request.args.get("data_inicio"))
    data_fim = converter_data(request.args.get("data_fim"))

    query = ManutencaoVeiculo.query.join(Veiculo)

    if veiculo_id:
        query = query.filter(
            ManutencaoVeiculo.veiculo_id == veiculo_id
        )

    if tipo_manutencao:
        query = query.filter(
            ManutencaoVeiculo.tipo_manutencao.ilike(
                f"%{tipo_manutencao}%"
            )
        )

    if data_inicio:
        query = query.filter(
            ManutencaoVeiculo.data_manutencao >= data_inicio
        )

    if data_fim:
        query = query.filter(
            ManutencaoVeiculo.data_manutencao <= data_fim
        )

    manutencoes = query.order_by(
        ManutencaoVeiculo.data_manutencao.desc(),
        ManutencaoVeiculo.id.desc()
    ).all()

    dados = []

    for m in manutencoes:

        valor = m.valor or Decimal("0.00")

        dados.append([
            m.data_manutencao.strftime("%d/%m/%Y") if m.data_manutencao else "-",
            f"{m.veiculo.marca} {m.veiculo.modelo}" if m.veiculo else "-",
            m.veiculo.placa if m.veiculo else "-",
            m.tipo_manutencao or "-",
            str(m.quilometragem or "-"),
            f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            m.oficina or "-",
            m.responsavel or "-",
            m.observacao or "-"
        ])

    if not dados:
        dados.append([
            "-", "-", "-", "-", "-", "-", "-", "-", "-"
        ])

    pdf = gerar_pdf_frota(
        "Histórico de Manutenções",
        [
            "Data",
            "Veículo",
            "Placa",
            "Tipo",
            "KM",
            "Valor",
            "Oficina",
            "Responsável",
            "Observação"
        ],
        dados
    )

    return send_file(
        pdf,
        as_attachment=True,
        download_name="historico_manutencoes.pdf",
        mimetype="application/pdf"
    )


# ==================================================
# PDF - HISTÓRICO DE ABASTECIMENTOS
# ==================================================
@frota_bp.route("/abastecimentos/pdf")
@login_required
def pdf_abastecimentos():

    veiculo_id = request.args.get("veiculo_id", type=int)
    data_inicio = converter_data(request.args.get("data_inicio"))
    data_fim = converter_data(request.args.get("data_fim"))

    query = AbastecimentoVeiculo.query.join(Veiculo)

    if veiculo_id:
        query = query.filter(AbastecimentoVeiculo.veiculo_id == veiculo_id)

    if data_inicio:
        query = query.filter(AbastecimentoVeiculo.data_abastecimento >= data_inicio)

    if data_fim:
        query = query.filter(AbastecimentoVeiculo.data_abastecimento <= data_fim)

    abastecimentos = query.order_by(
        AbastecimentoVeiculo.data_abastecimento.desc(),
        AbastecimentoVeiculo.id.desc()
    ).all()

    dados = []

    for a in abastecimentos:
        dados.append([
            a.data_abastecimento.strftime("%d/%m/%Y") if a.data_abastecimento else "-",
            f"{a.veiculo.marca} {a.veiculo.modelo}" if a.veiculo else "-",
            a.veiculo.placa if a.veiculo else "-",
            str(a.quilometragem or "-"),
            str(a.litros or "-"),
            f"R$ {a.valor_total or 0}",
            a.posto or "-",
            a.responsavel or "-",
            a.observacao or "-"
        ])

    pdf = gerar_pdf_frota(
        "Histórico de Abastecimentos",
        ["Data", "Veículo", "Placa", "KM", "Litros", "Valor", "Posto", "Responsável", "Observação"],
        dados or [["-", "-", "-", "-", "-", "-", "-", "-", "-"]]
    )

    return send_file(
        pdf,
        as_attachment=True,
        download_name="historico_abastecimentos.pdf",
        mimetype="application/pdf"
    )


