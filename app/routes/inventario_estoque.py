from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import (
    Estoque,
    Item,
    TipoServico,
    Empresa,
    InventarioEstoque,
    InventarioEstoqueItem
)

bp = Blueprint(
    'inventario_estoque',
    __name__,
    url_prefix='/inventario_estoque'
)


@bp.route('/', methods=['GET'])
@login_required
def inventario():

    tipo_estoque = request.args.get('tipo_estoque', 'empresa')
    cliente_id = request.args.get('cliente_id', type=int)
    tipo_servico_filtro = request.args.get('tipo_servico')
    categoria_filtro = request.args.get('categoria', '').strip().upper()
    
    clientes = (
        Empresa.query
        .filter_by(tipo_empresa="cliente")
        .order_by(Empresa.razao_social.asc())
        .all()
    )

    tipos_servico = (
        TipoServico.query
        .order_by(TipoServico.nome.asc())
        .all()
    )

    query = (
        db.session.query(Estoque, Item, TipoServico)
        .join(Item, Estoque.item_id == Item.id)
        .outerjoin(TipoServico, Estoque.tipo_servico_id == TipoServico.id)
    )

    if tipo_estoque == "cliente":

        if not cliente_id:
            return render_template(
                'estoque/inventario.html',
                resultados=[],
                clientes=clientes,
                tipos_servico=tipos_servico,
                tipo_estoque=tipo_estoque,
                cliente_id=cliente_id,
                tipo_servico_filtro=tipo_servico_filtro,
                categoria_filtro=categoria_filtro,
                data_hoje=datetime.now().strftime('%Y-%m-%d')                
            )

        query = query.filter(
            Estoque.tipo_estoque == "cliente",
            Estoque.cliente_id == cliente_id
        )

    else:
        tipo_estoque = "empresa"

        query = query.filter(
            db.or_(
                Estoque.tipo_estoque == "empresa",
                Estoque.tipo_estoque == None
            )
        )

    if tipo_servico_filtro and tipo_servico_filtro.isdigit():
        query = query.filter(
            Estoque.tipo_servico_id == int(tipo_servico_filtro)
        )

    if categoria_filtro in ['MATERIAL', 'FERRAMENTA', 'EPI']:
        query = query.filter(
            Item.categoria == categoria_filtro
        )

    resultados = query.all()

    resultados = [
        (estoque, item, tipo)
        for estoque, item, tipo in resultados
        if (estoque.quantidade or 0) > 0
    ]

    return render_template(
        'estoque/inventario.html',
        resultados=resultados,
        clientes=clientes,
        tipos_servico=tipos_servico,
        tipo_estoque=tipo_estoque,
        cliente_id=cliente_id,
        tipo_servico_filtro=tipo_servico_filtro,
        categoria_filtro=categoria_filtro,
        data_hoje=datetime.now().strftime('%Y-%m-%d')
    )

# ===================== Finalizar Inventário =====================
@bp.route('/finalizar', methods=['POST'])
@login_required
def finalizar_inventario():

    try:

        observacao = request.form.get('observacao', '').strip()
        tipo_servico_id = request.form.get('tipo_servico')

        responsavel_logado = (
            getattr(current_user, 'nome', None)
            or getattr(current_user, 'username', None)
            or getattr(current_user, 'email', None)
            or 'Usuário'
        )

        inventario = InventarioEstoque(
            data_hora=datetime.now(),
            responsavel=responsavel_logado,
            observacao=observacao,
            tipo_servico_id=int(tipo_servico_id)
            if tipo_servico_id else None
        )

        db.session.add(inventario)
        db.session.flush()

        alterou_algo = False

        for key, value in request.form.items():

            if not key.startswith('contada_'):
                continue

            if not value or value.strip() == '':
                continue

            try:
                quantidade_contada = int(value)

            except ValueError:
                continue

            estoque_id = key.replace('contada_', '')

            if not estoque_id.isdigit():
                continue

            estoque = Estoque.query.get(int(estoque_id))

            if not estoque:
                continue

            alterou_algo = True

            quantidade_antes = estoque.quantidade or 0

            estoque.quantidade = quantidade_contada

            item_inventariado = InventarioEstoqueItem(
                inventario_id=inventario.id,
                item_id=estoque.item_id,
                quantidade_estoque=quantidade_antes,
                quantidade_contada=quantidade_contada
            )

            if hasattr(InventarioEstoqueItem, 'usuario_id'):
                item_inventariado.usuario_id = current_user.id

            db.session.add(item_inventariado)

        if not alterou_algo:

            db.session.rollback()

            flash(
                'Nenhum item foi contado. Nenhuma alteração realizada.',
                'warning'
            )

            return redirect(
                url_for('inventario_estoque.inventario')
            )

        db.session.commit()

        flash(
            'Inventário finalizado com sucesso! Saldos atualizados.',
            'success'
        )

        return redirect(
            url_for('inventario_estoque.historico_inventarios')
        )

    except Exception as e:

        db.session.rollback()

        print("ERRO INVENTÁRIO:", e)

        flash(
            'Erro ao salvar inventário!',
            'danger'
        )

        return redirect(
            url_for('inventario_estoque.inventario')
        )


# ===================== Histórico =====================
@bp.route('/historico')
@login_required
def historico_inventarios():

    responsavel = request.args.get('responsavel', '').strip()
    data_filtro = request.args.get('data', '').strip()

    page = request.args.get(
        'page',
        1,
        type=int
    )

    query = InventarioEstoque.query

    if responsavel:

        query = query.filter(
            InventarioEstoque.responsavel.ilike(
                f"%{responsavel}%"
            )
        )

    if data_filtro:

        query = query.filter(
            db.func.date(
                InventarioEstoque.data_hora
            ) == data_filtro
        )

    inventarios = (
        query
        .order_by(
            InventarioEstoque.data_hora.desc()
        )
        .paginate(
            page=page,
            per_page=10,
            error_out=False
        )
    )

    return render_template(
        'estoque/inventario_historico.html',
        inventarios=inventarios,
        responsavel=responsavel,
        data_filtro=data_filtro
    )


# ===================== Detalhes =====================
@bp.route('/historico/<int:inventario_id>')
@login_required
def historico_inventario_detalhe(inventario_id):

    inventario = InventarioEstoque.query.get_or_404(
        inventario_id
    )

    itens = (
        db.session.query(
            Item.codigo,
            Item.descricao,
            Item.unidade,
            Item.categoria,
            InventarioEstoqueItem.quantidade_estoque,
            InventarioEstoqueItem.quantidade_contada
        )

        .join(
            Item,
            InventarioEstoqueItem.item_id == Item.id
        )

        .filter(
            InventarioEstoqueItem.inventario_id == inventario.id
        )

        .all()
    )

    return render_template(
        'estoque/inventario_historico_detalhe.html',
        inventario=inventario,
        itens=itens
    )
    
    # ===================== Exportar Detalhe Inventário Excel =====================
@bp.route('/historico/<int:inventario_id>/excel')
@login_required
def exportar_inventario_excel(inventario_id):
    import io
    import pandas as pd
    from flask import send_file

    inventario = InventarioEstoque.query.get_or_404(
        inventario_id
    )

    itens = (
        db.session.query(
            Item.codigo,
            Item.descricao,
            Item.unidade,
            InventarioEstoqueItem.quantidade_estoque,
            InventarioEstoqueItem.quantidade_contada
        )
        .join(
            Item,
            InventarioEstoqueItem.item_id == Item.id
        )
        .filter(
            InventarioEstoqueItem.inventario_id == inventario.id
        )
        .all()
    )

    dados = []

    for item in itens:
        dados.append({
            "Código": item.codigo,
            "Descrição": item.descricao,
            "Unidade": item.unidade,
            "Qtd. Anterior": item.quantidade_estoque,
            "Qtd. Contada": item.quantidade_contada
        })

    df = pd.DataFrame(dados)

    if df.empty:
        df = pd.DataFrame(columns=[
            "Código",
            "Descrição",
            "Unidade",
            "Qtd. Anterior",
            "Qtd. Contada"
        ])

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet("Inventário")
        writer.sheets["Inventário"] = worksheet

        titulo_format = workbook.add_format({
            "bold": True,
            "font_size": 14,
            "font_color": "white",
            "bg_color": "#002B55",
            "align": "center",
            "valign": "vcenter",
            "border": 1
        })

        info_format = workbook.add_format({
            "bold": True,
            "font_color": "#002B55",
            "bg_color": "#EAF2FB",
            "border": 1,
            "valign": "vcenter"
        })

        header_format = workbook.add_format({
            "bold": True,
            "font_color": "white",
            "bg_color": "#002B55",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        normal_format = workbook.add_format({
            "border": 1,
            "valign": "vcenter"
        })

        center_format = workbook.add_format({
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        alerta_format = workbook.add_format({
            "bold": True,
            "bg_color": "#FFF3CD",
            "font_color": "#664D03",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        worksheet.merge_range(
            "A1:E1",
            "DETALHES DO INVENTÁRIO DE ESTOQUE",
            titulo_format
        )

        worksheet.write("A3", "Responsável:", info_format)
        worksheet.write(
            "B3",
            inventario.responsavel or "-",
            normal_format
        )

        worksheet.write("D3", "Tipo de Serviço:", info_format)
        worksheet.write(
            "E3",
            inventario.tipo_servico.nome
            if inventario.tipo_servico
            else "-",
            normal_format
        )

        worksheet.write("A4", "Data/Hora:", info_format)
        worksheet.write(
            "B4",
            inventario.data_hora.strftime("%d/%m/%Y %H:%M")
            if inventario.data_hora
            else "-",
            normal_format
        )

        worksheet.write("D4", "Total de Itens:", info_format)
        worksheet.write(
            "E4",
            len(dados),
            center_format
        )

        worksheet.write("A5", "Observação:", info_format)
        worksheet.merge_range(
            "B5:E5",
            inventario.observacao or "-",
            normal_format
        )

        linha_header = 7

        for col_num, coluna in enumerate(df.columns):
            worksheet.write(
                linha_header,
                col_num,
                coluna,
                header_format
            )

        for row_num, item in enumerate(
            dados,
            start=linha_header + 1
        ):
            worksheet.write(row_num, 0, item["Código"], center_format)
            worksheet.write(row_num, 1, item["Descrição"], normal_format)
            worksheet.write(row_num, 2, item["Unidade"], center_format)

            worksheet.write(
                row_num,
                3,
                item["Qtd. Anterior"],
                center_format
            )

            if item["Qtd. Contada"] != item["Qtd. Anterior"]:
                worksheet.write(
                    row_num,
                    4,
                    item["Qtd. Contada"],
                    alerta_format
                )
            else:
                worksheet.write(
                    row_num,
                    4,
                    item["Qtd. Contada"],
                    center_format
                )

        worksheet.set_column("A:A", 18)
        worksheet.set_column("B:B", 45)
        worksheet.set_column("C:C", 14)
        worksheet.set_column("D:E", 18)

        worksheet.set_row(0, 26)
        worksheet.set_row(linha_header, 22)

        worksheet.freeze_panes(linha_header + 1, 0)

        worksheet.autofilter(
            linha_header,
            0,
            linha_header + len(dados),
            len(df.columns) - 1
        )

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"inventario_estoque_{inventario.id}.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )