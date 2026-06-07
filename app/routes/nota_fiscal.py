from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from app import db
from sqlalchemy import func
from app.models import (
    NotaFiscalEntrada,
    NotaFiscalItem,
    Item,
    Estoque,
    TipoServico,
    Empresa,
    OrdemServico
)

from flask_login import current_user
from datetime import datetime
import os

bp = Blueprint('nota_fiscal', __name__, url_prefix='/nota')

# ------------------------
# Função auxiliar para converter valores BR
# ------------------------
def parse_valor_br(valor_str):
    """Converte valores brasileiros (1.234,56) em float corretamente"""
    valor_str = str(valor_str).replace('R$', '').strip()
    if ',' in valor_str:
        valor_str = valor_str.replace('.', '').replace(',', '.')
    return float(valor_str)

# ------------------------
# Nova Nota Fiscal
# ------------------------
@bp.route('/nova', methods=['GET', 'POST'])
def nova_nota():
    if request.method == 'POST':
        numero_nf = request.form.get('numero_nf', '').strip()
        fornecedor = request.form.get('fornecedor', '').strip()
        tipo_estoque = request.form.get('tipo_estoque', '').strip()

        categoria_entrada = request.form.get(
            'categoria_entrada',
            'MATERIAL'
        ).strip().upper()

        cliente_id_raw = request.form.get('cliente_id')
        ordem_servico_id_raw = request.form.get('ordem_servico_id')
        tipo_servico_id_raw = request.form.get('tipo_servico_id')

        cliente_id = int(cliente_id_raw) if cliente_id_raw else None

        ordem_servico_id = (
            int(ordem_servico_id_raw)
            if ordem_servico_id_raw
            else None
        )

        tipo_servico_id = (
            int(tipo_servico_id_raw)
            if tipo_servico_id_raw
            else None
        )

        observacao = request.form.get('observacao', '').strip()

        if not numero_nf:
            flash('Informe o número da nota fiscal.', 'warning')
            return redirect(url_for('nota_fiscal.nova_nota'))

        if not fornecedor:
            flash('Informe o fornecedor.', 'warning')
            return redirect(url_for('nota_fiscal.nova_nota'))

        if tipo_estoque not in ['empresa', 'cliente']:
            flash('Selecione o tipo de estoque.', 'warning')
            return redirect(url_for('nota_fiscal.nova_nota'))

        # Cliente e O.S só são obrigatórios no estoque do cliente
        if tipo_estoque == 'cliente':
            if not cliente_id:
                flash('Selecione o cliente.', 'warning')
                return redirect(url_for('nota_fiscal.nova_nota'))

            # O.S não é mais obrigatória
            ordem_servico_id = None

        else:
            cliente_id = None
            ordem_servico_id = None

        if NotaFiscalEntrada.query.filter_by(numero_nf=numero_nf).first():
            flash('Já existe uma nota fiscal com este número.', 'danger')
            return redirect(url_for('nota_fiscal.nova_nota'))

        tipo_servico_nome = ''

        if categoria_entrada == 'MATERIAL':

            if not tipo_servico_id:
                flash('Selecione o tipo de serviço.', 'warning')
                return redirect(url_for('nota_fiscal.nova_nota'))

            tipo_servico_obj = TipoServico.query.get(tipo_servico_id)

            # ==========================================
            # BLOQUEIO PARA ESTOQUE EMPRESA
            # Manutenção e Reparo não recebem entrada própria
            # ==========================================
            if (
                tipo_estoque == "empresa"
                and tipo_servico_obj
                and tipo_servico_obj.nome.strip().lower() in [
                    "manutenção",
                    "manutencao",
                    "reparo"
                ]
            ):
                flash(
                    "Não é permitida entrada de materiais para este Tipo de Serviço.",
                    "warning"
                )
                return redirect(url_for('nota_fiscal.nova_nota'))

            tipo_servico_nome = (
                tipo_servico_obj.nome
                if tipo_servico_obj
                else ''
            )

        else:
            tipo_servico_obj = TipoServico.query.get(tipo_servico_id) if tipo_servico_id else None

            tipo_servico_nome = (
                tipo_servico_obj.nome
                if tipo_servico_obj
                else ''
            )

        codigos = request.form.getlist('codigo[]')
        descricoes = request.form.getlist('descricao[]')
        quantidades = request.form.getlist('quantidade[]')
        valores = request.form.getlist('valor[]')

        enderecos = (
            request.form.getlist('endereco[]')
            if 'endereco[]' in request.form
            else [''] * len(codigos)
        )

        nova_nota = NotaFiscalEntrada(
            numero_nf=numero_nf,
            fornecedor=fornecedor,
            tipo_estoque=tipo_estoque,
            cliente_id=cliente_id,
            ordem_servico_id=ordem_servico_id,
            tipo_servico=tipo_servico_nome,
            tipo_servico_id=tipo_servico_id,
            usuario_id=current_user.id if current_user.is_authenticated else None,
            observacao=observacao,
            data_hora=datetime.utcnow()
        )

        db.session.add(nova_nota)
        db.session.flush()

        itens_processados = 0
        itens_ignorados = 0

        for i in range(len(codigos)):
            codigo = (codigos[i] or '').strip()
            descricao_item = descricoes[i] if i < len(descricoes) else ''
            qtd = quantidades[i] if i < len(quantidades) else 0
            val = valores[i] if i < len(valores) else 0
            endereco = enderecos[i] if i < len(enderecos) else ''

            if not codigo:
                itens_ignorados += 1
                continue

            try:
                quantidade_int = int(float(qtd))
                if quantidade_int <= 0:
                    itens_ignorados += 1
                    continue
            except Exception:
                itens_ignorados += 1
                continue

            try:
                valor_convertido = parse_valor_br(val)
            except Exception:
                valor_convertido = 0.0

            item = Item.query.filter_by(codigo=codigo).first()

            if not item:
                item = Item(
                    codigo=codigo,
                    descricao=(
                        descricao_item
                        if descricao_item
                        else f"ITEM {codigo}"
                    ),
                    valor=valor_convertido,
                    unidade="UN",
                    categoria=categoria_entrada,
                    eh_equipamento=categoria_entrada in [
                        'FERRAMENTA',
                        'EPI'
                    ]
                )
                db.session.add(item)
                db.session.flush()

            else:
                if descricao_item and descricao_item != item.descricao:
                    item.descricao = descricao_item

                item.categoria = categoria_entrada
                item.eh_equipamento = categoria_entrada in [
                    'FERRAMENTA',
                    'EPI'
                ]

            nota_item = NotaFiscalItem(
                nota_fiscal_id=nova_nota.id,
                item_id=item.id,
                quantidade=quantidade_int,
                valor_unitario=valor_convertido
            )

            db.session.add(nota_item)

            estoque = Estoque.query.filter_by(
                item_id=item.id,
                tipo_servico_id=tipo_servico_id,
                tipo_estoque=tipo_estoque,
                cliente_id=(
                    cliente_id
                    if tipo_estoque == 'cliente'
                    else None
                )
            ).first()

            if estoque:
                estoque.quantidade += quantidade_int

                if endereco and endereco.strip():
                    estoque.endereco = endereco.strip()

            else:
                novo_estoque = Estoque(
                    item_id=item.id,
                    quantidade=quantidade_int,
                    quantidade_minima=0,
                    endereco=endereco.strip() if endereco else '',
                    tipo_servico_id=tipo_servico_id,
                    tipo_estoque=tipo_estoque,
                    cliente_id=(
                        cliente_id
                        if tipo_estoque == 'cliente'
                        else None
                    )
                )

                db.session.add(novo_estoque)

            itens_processados += 1

        db.session.commit()

        flash(
            f'Nota fiscal registrada com sucesso! ✅ '
            f'{itens_processados} itens processados | '
            f'{itens_ignorados} ignorados.',
            'success'
        )

        return redirect(url_for('nota_fiscal.historico'))

    itens = Item.query.all()
    tipos_servico = TipoServico.query.all()

    fornecedores = Empresa.query.filter_by(
        tipo_empresa="fornecedor"
    ).order_by(Empresa.razao_social).all()

    clientes = Empresa.query.filter_by(
        tipo_empresa="cliente"
    ).order_by(Empresa.razao_social).all()

    ordens_servico = OrdemServico.query.filter(
        OrdemServico.cliente_id.isnot(None)
    ).order_by(
        OrdemServico.numero_os.asc()
    ).all()

    return render_template(
        'nota_fiscal/nova.html',
        itens=itens,
        tipos_servico=tipos_servico,
        fornecedores=fornecedores,
        clientes=clientes,
        ordens_servico=ordens_servico
    )
# ------------------------
# Histórico
# ------------------------
@bp.route('/historico')
def historico():
    tipo_servico_id = request.args.get('tipo_servico', type=int)
    tipo_estoque = request.args.get('tipo_estoque', '').strip()

    query = NotaFiscalEntrada.query

    if tipo_estoque in ['empresa', 'cliente']:
        query = query.filter(NotaFiscalEntrada.tipo_estoque == tipo_estoque)

    if tipo_servico_id:
        query = query.filter(NotaFiscalEntrada.tipo_servico_id == tipo_servico_id)

    notas = query.order_by(NotaFiscalEntrada.data_hora.desc()).all()
    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    return render_template(
        'nota_fiscal/historico.html',
        notas=notas,
        tipos_servico=tipos_servico,
        tipo_servico_id=tipo_servico_id,
        tipo_estoque=tipo_estoque
    )

# ------------------------
# Detalhes
# ------------------------
@bp.route('/<int:id>')
def detalhes(id):
    nota = NotaFiscalEntrada.query.get_or_404(id)
    itens = NotaFiscalItem.query.filter_by(nota_fiscal_id=nota.id).all()
    total_nota = sum(item.quantidade * item.valor_unitario for item in itens)

    return render_template(
        'nota_fiscal/detalhes.html',
        nota=nota,
        itens=itens,
        total_nota=total_nota
    )

# ------------------------
# Exportar Nota em PDF
# ------------------------
@bp.route('/<int:id>/pdf', endpoint='exportar_pdf')
def exportar_pdf(id):
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer
    )

    nota = NotaFiscalEntrada.query.get_or_404(id)
    itens_nf = NotaFiscalItem.query.filter_by(nota_fiscal_id=nota.id).all()

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm
    )

    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "Titulo",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.HexColor("#002b55"),
        alignment=1,
        spaceAfter=12
    )

    normal = styles["Normal"]
    normal.fontSize = 9

    elementos = []

    elementos.append(
        Paragraph("NOTA FISCAL DE ENTRADA", titulo_style)
    )

    tipo_estoque = "Cliente" if nota.tipo_estoque == "cliente" else "Empresa"

    dados_cabecalho = [
        ["Número NF", nota.numero_nf or nota.id],
        ["Fornecedor", nota.fornecedor or ""],
        ["Tipo de Estoque", tipo_estoque],
        ["Cliente", nota.cliente.razao_social if nota.cliente else ""],
        [
            "Tipo de Serviço",
            nota.tipo_servico_ref.nome
            if getattr(nota, "tipo_servico_ref", None)
            else nota.tipo_servico or ""
        ],
        ["Registrado por", nota.usuario.nome if nota.usuario else ""],
        [
            "Data Registro",
            nota.data_hora.strftime("%d/%m/%Y %H:%M")
            if nota.data_hora
            else ""
        ],
        ["Observação", nota.observacao or ""]
    ]

    tabela_cabecalho = Table(
        dados_cabecalho,
        colWidths=[4 * cm, 22 * cm]
    )

    tabela_cabecalho.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9eef5")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#002b55")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    elementos.append(tabela_cabecalho)
    elementos.append(Spacer(1, 12))

    dados_itens = [[
        "Código",
        "Descrição",
        "Unidade",
        "Qtd",
        "Valor Unit.",
        "Subtotal"
    ]]

    total = 0.0

    for ni in itens_nf:
        produto = Item.query.get(ni.item_id)

        codigo = produto.codigo if produto else ""
        descricao = produto.descricao if produto else ""
        unidade = getattr(produto, "unidade", "") if produto else ""

        quantidade = float(ni.quantidade or 0)
        valor_unitario = float(ni.valor_unitario or 0)
        subtotal = quantidade * valor_unitario
        total += subtotal

        dados_itens.append([
            codigo,
            Paragraph(descricao, normal),
            unidade,
            f"{quantidade:.0f}",
            f"R$ {valor_unitario:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"R$ {subtotal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ])

    dados_itens.append([
        "",
        "",
        "",
        "",
        "TOTAL",
        f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    ])

    tabela_itens = Table(
        dados_itens,
        colWidths=[
            3 * cm,
            12 * cm,
            3 * cm,
            2 * cm,
            4 * cm,
            4 * cm
        ],
        repeatRows=1
    )

    tabela_itens.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#002b55")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),

        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("ALIGN", (3, 1), (-1, -1), "CENTER"),

        ("BACKGROUND", (4, -1), (-1, -1), colors.HexColor("#e9eef5")),
        ("FONTNAME", (4, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (4, -1), (-1, -1), colors.HexColor("#002b55")),
    ]))

    elementos.append(tabela_itens)

    doc.build(elementos)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = (
        f'inline; filename=nota_{nota.numero_nf or nota.id}.pdf'
    )

    return resp
# ------------------------
# Exportar Nota em Excel
# ------------------------
@bp.route('/<int:id>/excel', endpoint='exportar_excel')
def exportar_excel(id):
    nota = NotaFiscalEntrada.query.get_or_404(id)
    itens_nf = NotaFiscalItem.query.filter_by(
        nota_fiscal_id=nota.id
    ).all()

    import io
    import pandas as pd
    from flask import send_file

    output = io.BytesIO()

    dados = []
    total_geral = 0

    for ni in itens_nf:
        produto = Item.query.get(ni.item_id)

        quantidade = ni.quantidade or 0
        valor_unitario = float(ni.valor_unitario or 0)
        subtotal = quantidade * valor_unitario
        total_geral += subtotal

        dados.append({
            "Código": produto.codigo if produto else "",
            "Descrição": produto.descricao if produto else "",
            "Unidade de Medida": (
                getattr(produto, "unidade", "")
                if produto
                else ""
            ),
            "Quantidade": quantidade,
            "Valor Unitário": valor_unitario,
            "Subtotal": subtotal
        })

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet("Nota Fiscal")
        writer.sheets["Nota Fiscal"] = worksheet

        titulo_fmt = workbook.add_format({
            "bold": True,
            "font_size": 14,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#002b55",
            "font_color": "white",
            "border": 1
        })

        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1,
            "align": "center"
        })

        label_fmt = workbook.add_format({
            "bold": True,
            "border": 1,
            "bg_color": "#F2F2F2"
        })

        value_fmt = workbook.add_format({
            "border": 1
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

        total_fmt = workbook.add_format({
            "bold": True,
            "num_format": 'R$ #,##0.00',
            "border": 1,
            "bg_color": "#D9EAF7"
        })

        worksheet.merge_range(
            "A1:F1",
            "NOTA FISCAL DE ENTRADA",
            titulo_fmt
        )

        cabecalho = [
            ("Número NF", nota.numero_nf or ""),
            ("Fornecedor", nota.fornecedor or ""),
            (
                "Tipo de Estoque",
                "Cliente"
                if nota.tipo_estoque == "cliente"
                else "Empresa"
            )
        ]

        if nota.tipo_estoque == "cliente":
            cabecalho.append((
                "Cliente",
                nota.cliente.razao_social
                if nota.cliente
                else ""
            ))

            cabecalho.append((
                "O.S / Local",
                nota.ordem_servico.numero_os
                if nota.ordem_servico
                else ""
            ))

        cabecalho.extend([
            (
                "Tipo de Serviço",
                nota.tipo_servico_ref.nome
                if nota.tipo_servico_ref
                else nota.tipo_servico or ""
            ),
            (
                "Registrado por",
                nota.usuario.nome
                if nota.usuario
                else ""
            ),
            (
                "Data Registro",
                nota.data_hora.strftime("%d/%m/%Y %H:%M")
                if nota.data_hora
                else ""
            ),
            ("Observação", nota.observacao or "")
        ])

        row = 2

        for label, value in cabecalho:
            worksheet.write(row, 0, label, label_fmt)
            worksheet.merge_range(
                row,
                1,
                row,
                5,
                value,
                value_fmt
            )
            row += 1

        row += 1

        colunas = [
            "Código",
            "Descrição",
            "Unidade de Medida",
            "Quantidade",
            "Valor Unitário",
            "Subtotal"
        ]

        for col, nome_coluna in enumerate(colunas):
            worksheet.write(
                row,
                col,
                nome_coluna,
                header_fmt
            )

        row += 1

        for item in dados:
            worksheet.write(row, 0, item["Código"], value_fmt)
            worksheet.write(row, 1, item["Descrição"], value_fmt)
            worksheet.write(row, 2, item["Unidade de Medida"], value_fmt)
            worksheet.write(row, 3, item["Quantidade"], int_fmt)
            worksheet.write(row, 4, item["Valor Unitário"], money_fmt)
            worksheet.write(row, 5, item["Subtotal"], money_fmt)
            row += 1

        worksheet.merge_range(
            row,
            0,
            row,
            4,
            "TOTAL DA NOTA",
            label_fmt
        )

        worksheet.write(
            row,
            5,
            total_geral,
            total_fmt
        )

        worksheet.set_column("A:A", 18)
        worksheet.set_column("B:B", 45)
        worksheet.set_column("C:C", 20)
        worksheet.set_column("D:D", 14)
        worksheet.set_column("E:F", 18)

        worksheet.freeze_panes(row - len(dados), 0)

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"nota_{nota.numero_nf or nota.id}.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
# ------------------------
# Pesquisar Nota Fiscal
# ------------------------
@bp.route('/pesquisar', methods=['GET'])
def pesquisar():

    numero = request.args.get('numero', '').strip()
    fornecedor = request.args.get('fornecedor', '').strip()
    data_emissao = request.args.get('data_emissao', '').strip()
    tipo_estoque = request.args.get('tipo_estoque', '').strip()
    categoria = request.args.get('categoria', '').strip().upper()

    query = NotaFiscalEntrada.query

    # 🔎 filtro por número NF
    if numero:
        query = query.filter(
            NotaFiscalEntrada.numero_nf.ilike(f'%{numero}%')
        )

    # 🔎 filtro por fornecedor
    if fornecedor:
        query = query.filter(
            NotaFiscalEntrada.fornecedor.ilike(f'%{fornecedor}%')
        )

    # 🔎 filtro por tipo de estoque
    if tipo_estoque:
        query = query.filter(
            NotaFiscalEntrada.tipo_estoque == tipo_estoque
        )

    # 🔎 filtro por data
    if data_emissao:
        try:
            data = datetime.strptime(data_emissao, '%Y-%m-%d')

            query = query.filter(
                db.func.date(NotaFiscalEntrada.data_hora) == data.date()
            )

        except:
            pass

    notas = query.order_by(
        NotaFiscalEntrada.data_hora.desc()
    ).all()

    # 🔥 cálculo dos totais
    notas_com_totais = []

    for nota in notas:

        itens = NotaFiscalItem.query.filter_by(
            nota_fiscal_id=nota.id
        ).all()

        # =========================
        # CATEGORIA DA NOTA
        # =========================
        categoria_nota = 'MATERIAL'

        if itens and itens[0].item and itens[0].item.categoria:
            categoria_nota = itens[0].item.categoria.upper()

        # 🔥 FILTRO POR CATEGORIA
        if categoria and categoria_nota != categoria:
            continue

        total_nota = sum(
            i.quantidade * i.valor_unitario
            for i in itens
        )

        total_itens = sum(
            i.quantidade
            for i in itens
        )

        notas_com_totais.append({
            'nota': nota,
            'total_nota': total_nota,
            'total_itens': total_itens
        })

    return render_template(
        'nota_fiscal/pesquisar.html',
        notas=notas_com_totais,
        numero=numero,
        fornecedor=fornecedor,
        data_emissao=data_emissao,
        tipo_estoque=tipo_estoque,
        categoria=categoria
    )
# ------------------------
# API: Buscar Item
# ------------------------
@bp.route('/api/item/<codigo>')
def api_buscar_item(codigo):
    item = Item.query.filter_by(codigo=codigo).first()
    if item:
        return jsonify({
            'success': True,
            'descricao': item.descricao,
            'valor': item.valor
        })
    return jsonify({'success': False})

# ------------------------
# API: Buscar responsável do projeto
# ------------------------
@bp.route('/api/responsavel/<int:tipo_servico_id>')
def api_responsavel(tipo_servico_id):
    tipo = TipoServico.query.get(tipo_servico_id)
    return jsonify({'responsavel': tipo.responsavel if tipo and tipo.responsavel else ''})

# ------------------------
# Excluir Nota Fiscal
# ------------------------
@bp.route('/excluir/<int:id>', methods=['POST'])
def excluir_nota(id):
    nota = NotaFiscalEntrada.query.get_or_404(id)

    itens = NotaFiscalItem.query.filter_by(nota_fiscal_id=nota.id).all()
    for item in itens:
        db.session.delete(item)

    db.session.delete(nota)
    db.session.commit()

    flash('Nota fiscal excluída com sucesso!', 'success')
    return redirect(url_for('nota_fiscal.historico'))

@bp.route('/api/ordens_servico/<int:cliente_id>')
def api_ordens_servico_cliente(cliente_id):
    ordens = OrdemServico.query.filter_by(
        cliente_id=cliente_id
    ).order_by(
        OrdemServico.numero_os.asc()
    ).all()

    return jsonify([
        {
            "id": os.id,
            "numero_os": os.numero_os
        }
        for os in ordens
    ])

# ------------------------
# API: Listar todos os itens cadastrados
# ------------------------
@bp.route('/api/itens')
def api_itens():

    categoria = request.args.get('categoria', '').strip().lower()

    query = Item.query

    if categoria:
        query = query.filter(
            func.lower(Item.categoria) == categoria
        )

    itens = query.order_by(Item.descricao.asc()).all()

    return jsonify([
        {
            'codigo': item.codigo,
            'descricao': item.descricao,
            'valor': item.valor
        }
        for item in itens
    ])
