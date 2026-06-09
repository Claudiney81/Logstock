from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import Item, Estoque, TipoServico
import pandas as pd
from flask_login import login_required

bp = Blueprint('estoque', __name__, url_prefix='/estoque')


# ------------------------
# Cadastro de Item Manual
# ------------------------
@bp.route('/cadastro', methods=['GET', 'POST'])
@login_required
def cadastrar_item():
    if request.method == 'POST':
        codigo = request.form['codigo'].strip().upper()
        descricao = request.form['descricao'].strip()
        unidade = request.form['unidade'].strip()

        valor = converter_valor(request.form.get('valor', '0'))

        categoria = request.form.get('categoria', 'MATERIAL').strip().upper()

        if categoria not in ['MATERIAL', 'FERRAMENTA', 'EPI']:
            categoria = 'MATERIAL'

        # Verifica duplicidade
        if Item.query.filter_by(codigo=codigo).first():
            flash('Já existe um item com este código.', 'warning')
            return redirect(url_for('estoque.cadastrar_item'))

        novo_item = Item(
            codigo=codigo,
            descricao=descricao,
            unidade=unidade,
            valor=valor,
            categoria=categoria,
            eh_equipamento=categoria in ['FERRAMENTA', 'EPI']
        )

        db.session.add(novo_item)
        db.session.commit()

        flash('Item cadastrado com sucesso!', 'success')
        return redirect(url_for('estoque.cadastrar_item'))

    return render_template('estoque/cadastro.html')

# ------------------------
# Listar Itens
# ------------------------
@bp.route('/listar', methods=['GET'])
@login_required
def listar_itens():
    codigo = request.args.get('codigo', '').strip()
    descricao = request.args.get('descricao', '').strip()
    categoria = request.args.get('categoria', '').strip().upper()

    query = Item.query

    if codigo:
        query = query.filter(Item.codigo.ilike(f'%{codigo}%'))

    if descricao:
        query = query.filter(Item.descricao.ilike(f'%{descricao}%'))

    if categoria:
        query = query.filter(Item.categoria == categoria)

    itens = query.order_by(Item.descricao.asc()).all()

    return render_template(
        'estoque/listar.html',
        itens=itens,
        codigo=codigo,
        descricao=descricao,
        categoria=categoria
    )

# ------------------------
# Importar Itens via Excel
# ------------------------
def converter_valor(valor_raw):
    if valor_raw is None:
        return 0.0

    valor_str = str(valor_raw).strip()

    valor_str = (
        valor_str
        .replace('R$', '')
        .replace(' ', '')
    )

    if valor_str == '' or valor_str.lower() == 'nan':
        return 0.0

    # Formato brasileiro: 1.234,56
    if ',' in valor_str:
        valor_str = (
            valor_str
            .replace('.', '')
            .replace(',', '.')
        )
        return float(valor_str)

    # Formato Excel/Python: 1234.56
    return float(valor_str)


@bp.route('/importar', methods=['POST'])
@login_required
def importar_itens():
    arquivo = request.files.get('arquivo')
    
    categoria_importacao = request.form.get(
    'categoria_importacao',
    'MATERIAL'
    ).strip().upper()

    if categoria_importacao not in [
        'MATERIAL',
        'FERRAMENTA',
        'EPI'
    ]:
        categoria_importacao = 'MATERIAL'

    if not arquivo:
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('estoque.cadastrar_item'))

    try:
        df = pd.read_excel(arquivo)

        importados = 0
        atualizados = 0

        for _, row in df.iterrows():

            codigo = str(
                row.get(
                    'Código',
                    row.get(
                        'CODIGO',
                        row.get('codigo', '')
                    )
                )
            ).strip().upper()

            descricao = str(
                row.get(
                    'Descrição',
                    row.get(
                        'DESCRICAO',
                        row.get('descricao', '')
                    )
                )
            ).strip()

            unidade = str(
                row.get(
                    'Unidade de Medida',
                    row.get(
                        'Unidade',
                        row.get(
                            'UNIDADE',
                            row.get('unidade', '')
                        )
                    )
                )
            ).strip()

            valor_raw = row.get(
                'Valor',
                row.get(
                    'Valor Unitário',
                    row.get(
                        'VALOR',
                        row.get('valor', 0)
                    )
                )
            )

            categoria = categoria_importacao

            try:
                valor = converter_valor(valor_raw)
            except Exception:
                valor = 0.0

            if not codigo or codigo == 'NAN':
                continue

            if not descricao or descricao.upper() == 'NAN':
                descricao = 'ITEM IMPORTADO'

            if not unidade or unidade.upper() == 'NAN':
                unidade = 'UN'

            item_existente = Item.query.filter_by(codigo=codigo).first()

            if item_existente:
                item_existente.descricao = descricao
                item_existente.unidade = unidade
                item_existente.valor = valor
                item_existente.categoria = categoria
                item_existente.eh_equipamento = categoria in ['FERRAMENTA', 'EPI']
                atualizados += 1

            else:
                novo_item = Item(
                    codigo=codigo,
                    descricao=descricao,
                    unidade=unidade,
                    valor=valor,
                    categoria=categoria,
                    eh_equipamento=categoria in ['FERRAMENTA', 'EPI']
                )

                db.session.add(novo_item)
                importados += 1

        db.session.commit()

        flash(
            f'Importação concluída! Novos: {importados} | Atualizados: {atualizados}',
            'success'
        )

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao importar itens: {str(e)}', 'danger')

    return redirect(url_for('estoque.cadastrar_item'))


# ------------------------
# Alertas de Estoque
# ------------------------
@bp.route('/alertas')
@login_required
def alerta_estoque_baixo():

    tipo_servico_id = request.args.get("tipo_servico", type=int)

    alertas = buscar_alertas_estoque(tipo_servico_id)

    tipos_servico = (
        TipoServico.query
        .order_by(TipoServico.nome.asc())
        .all()
    )

    return render_template(
        'estoque/alertas.html',
        resultados=alertas,
        tipos_servico=tipos_servico,
        tipo_servico_filtro=tipo_servico_id
    )


# ------------------------
# Função auxiliar - Buscar Alertas de Estoque
# ------------------------
def buscar_alertas_estoque(tipo_servico_id=None):

    # ==================================================
    # REGRA OFICIAL:
    # Estoque Empresa só possui saldo em Instalação.
    # Manutenção e Reparo não exibem alertas.
    # ==================================================
    if tipo_servico_id:

        tipo_servico = TipoServico.query.get(tipo_servico_id)

        if tipo_servico and tipo_servico.nome.strip().lower() in [
            "manutenção",
            "manutencao",
            "reparo"
        ]:
            return []

    query = (
        db.session.query(Estoque, Item, TipoServico)
        .join(Item, Estoque.item_id == Item.id)
        .outerjoin(
            TipoServico,
            Estoque.tipo_servico_id == TipoServico.id
        )
        .filter(
            Estoque.tipo_estoque == 'empresa'
        )
    )

    if tipo_servico_id:
        query = query.filter(
            Estoque.tipo_servico_id == tipo_servico_id
        )

    resultados = query.all()

    alertas = []

    for estoque, item, tipo_servico in resultados:

        if (
            estoque.quantidade_minima is not None
            and estoque.quantidade_minima > 0
            and estoque.quantidade <= estoque.quantidade_minima
        ):
            alertas.append(
                (estoque, item, tipo_servico)
            )

    return alertas

# ------------------------
# API: Estoque
# ------------------------
@bp.route('/saldo', methods=['GET'])
@login_required
def saldo_estoque():

    from sqlalchemy import func
    from app.models import Empresa, TipoServico

    codigo = request.args.get('codigo', '').strip()
    descricao = request.args.get('descricao', '').strip()

    tipo_estoque = request.args.get("tipo_estoque")
    cliente_id = request.args.get("cliente_id", type=int)
    tipo_servico_id = request.args.get("tipo_servico_id", type=int)
    categoria = request.args.get("categoria", "").strip().upper()

    if tipo_estoque == "empresa" and not categoria:
        categoria = "MATERIAL"

    clientes = (
        Empresa.query
        .filter_by(tipo_empresa="cliente")
        .order_by(Empresa.razao_social)
        .all()
    )

    tipos_servico = (
        TipoServico.query
        .order_by(TipoServico.nome)
        .all()
    )

    if tipo_estoque not in ["empresa", "cliente"]:
        return render_template(
            'estoque/saldo.html',
            resultados=[],
            clientes=clientes,
            tipos_servico=tipos_servico,
            codigo=codigo,
            descricao=descricao,
            tipo_estoque=tipo_estoque,
            cliente_id=cliente_id,
            tipo_servico_id=tipo_servico_id,
            categoria=categoria
        )

    if tipo_estoque == "cliente" and not cliente_id:
        return render_template(
            'estoque/saldo.html',
            resultados=[],
            clientes=clientes,
            tipos_servico=tipos_servico,
            codigo=codigo,
            descricao=descricao,
            tipo_estoque=tipo_estoque,
            cliente_id=cliente_id,
            tipo_servico_id=tipo_servico_id,
            categoria=categoria
        )

    query = (
        db.session.query(
            Item.codigo,
            Item.descricao,
            Item.unidade,
            Item.categoria,
            Item.valor,
            func.sum(Estoque.quantidade).label('quantidade'),
            func.max(Estoque.quantidade_minima).label('quantidade_minima'),
            func.max(Estoque.endereco).label('endereco'),
            Estoque.item_id,
            Estoque.tipo_estoque,
            Estoque.cliente_id,
            Empresa.razao_social.label("cliente_nome")
        )
        .join(Item, Estoque.item_id == Item.id)
        .outerjoin(Empresa, Estoque.cliente_id == Empresa.id)
    )

    if codigo:
        query = query.filter(Item.codigo.ilike(f'%{codigo}%'))

    if descricao:
        query = query.filter(Item.descricao.ilike(f'%{descricao}%'))

    if categoria:
        query = query.filter(Item.categoria == categoria)

    # Tipo de estoque
    if tipo_estoque == "cliente":
        query = query.filter(
            Estoque.tipo_estoque == "cliente",
            Estoque.cliente_id == cliente_id
        )

    elif tipo_estoque == "empresa":
        query = query.filter(
            db.or_(
                Estoque.tipo_estoque == "empresa",
                Estoque.tipo_estoque == None
            )
        )

    # Tipo de serviço
    tipo_servico_consulta_id = tipo_servico_id

    # REGRA LOGISTOCK:
    # Manutenção/Reparo consultam saldo físico da Instalação.
    if tipo_servico_id in [2, 3, 5]:
        tipo_servico_consulta_id = 1

    if tipo_servico_consulta_id:
        query = query.filter(
            Estoque.tipo_servico_id == tipo_servico_consulta_id
        )

    resultados = (
        query
        .group_by(
            Estoque.item_id,
            Estoque.tipo_estoque,
            Estoque.cliente_id,
            Item.codigo,
            Item.descricao,
            Item.unidade,
            Item.categoria,
            Item.valor,
            Empresa.razao_social
        )
        .having(func.sum(Estoque.quantidade) > 0)
        .order_by(
            Empresa.razao_social,
            Item.descricao
        )
        .all()
    )

    return render_template(
        'estoque/saldo.html',
        resultados=resultados,
        clientes=clientes,
        tipos_servico=tipos_servico,
        codigo=codigo,
        descricao=descricao,
        tipo_estoque=tipo_estoque,
        cliente_id=cliente_id,
        tipo_servico_id=tipo_servico_id,
        categoria=categoria
    )

# ------------------------
# Atualização de Estoque Mínimo (SOMENTE mínimos)
# ------------------------
@bp.route('/atualizar_minimos', methods=['POST'])
@login_required
def atualizar_minimos():

    atualizados_minimos = 0

    tipo_estoque = request.args.get("tipo_estoque") or request.form.get("tipo_estoque")
    cliente_id = request.args.get("cliente_id", type=int) or request.form.get("cliente_id", type=int)
    tipo_servico_id = request.args.get("tipo_servico_id", type=int) or request.form.get("tipo_servico_id", type=int)

    for key, value in request.form.items():

        if not (key.startswith("minimos[") and key.endswith("]")):
            continue

        try:
            item_id = int(key[8:-1])
            val = (value or "").strip()

            query = Estoque.query.filter_by(
                item_id=item_id
            )

            if tipo_estoque == "empresa":
                query = query.filter(
                    Estoque.tipo_estoque == "empresa"
                )

                if tipo_servico_id:
                    query = query.filter(
                        Estoque.tipo_servico_id == tipo_servico_id
                    )

            elif tipo_estoque == "cliente":
                query = query.filter(
                    Estoque.tipo_estoque == "cliente"
                )

                if cliente_id:
                    query = query.filter(
                        Estoque.cliente_id == cliente_id
                    )

            estoques = query.all()

            if not estoques:
                continue

            for estoque in estoques:

                if val == "":
                    estoque.quantidade_minima = None

                elif val.endswith('%'):
                    percentual = int(val[:-1].strip())
                    estoque.quantidade_minima = round(
                        (percentual / 100) * (estoque.quantidade or 0)
                    )

                else:
                    estoque.quantidade_minima = int(val)

            atualizados_minimos += 1

        except Exception as e:
            print("ERRO MINIMO:", e)
            continue

    db.session.commit()

    flash(
        f'Estoque mínimo atualizado. Registros alterados: {atualizados_minimos}.',
        'success'
    )

    return redirect(url_for(
        'estoque.saldo_estoque',
        tipo_estoque=tipo_estoque,
        cliente_id=cliente_id,
        tipo_servico_id=tipo_servico_id
    ))


@bp.route('/atualizar_enderecos', methods=['POST'])
@login_required
def atualizar_enderecos():

    atualizados = 0

    tipo_estoque = request.form.get("tipo_estoque")
    cliente_id = request.form.get("cliente_id", type=int)
    tipo_servico_id = request.form.get("tipo_servico_id", type=int)

    for key, value in request.form.items():

        if not (key.startswith("enderecos[") and key.endswith("]")):
            continue

        try:
            item_id = int(key[10:-1])
            novo = (value or "").strip()

            query = Estoque.query.filter_by(item_id=item_id)

            if tipo_estoque == "empresa":
                query = query.filter(Estoque.tipo_estoque == "empresa")

                if tipo_servico_id:
                    query = query.filter(Estoque.tipo_servico_id == tipo_servico_id)

            elif tipo_estoque == "cliente":
                query = query.filter(Estoque.tipo_estoque == "cliente")

                if cliente_id:
                    query = query.filter(Estoque.cliente_id == cliente_id)

            estoques = query.all()

            for estoque in estoques:
                estoque.endereco = novo if novo else None

            if estoques:
                atualizados += 1

        except Exception as e:
            print("ERRO ENDERECO:", e)
            continue

    db.session.commit()

    flash(
        f'Endereços atualizados com sucesso! Registros alterados: {atualizados}.'
        if atualizados else 'Nenhuma alteração de endereço detectada.',
        'success' if atualizados else 'info'
    )

    return redirect(url_for(
        'estoque.saldo_estoque',
        tipo_estoque=tipo_estoque,
        cliente_id=cliente_id,
        tipo_servico_id=tipo_servico_id
    ))


# ------------------------
# Exportar Itens Cadastrados em Excel
# ------------------------
@bp.route('/exportar_excel')
@login_required
def exportar_excel_estoque():
    from flask import send_file
    import pandas as pd
    import io

    itens = Item.query.all()

    dados = []
    for item in itens:
        dados.append({
            "Código": item.codigo,
            "Descrição": item.descricao,
            "Unidade": item.unidade,
            "Valor (R$)": float(item.valor or 0),
            "Categoria": item.categoria or "MATERIAL"
        })

    df = pd.DataFrame(dados)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Itens Cadastrados')

        workbook = writer.book
        worksheet = writer.sheets['Itens Cadastrados']

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#002B55',
            'font_color': 'white',
            'border': 1
        })

        money_format = workbook.add_format({
            'num_format': 'R$ #,##0.00'
        })

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        worksheet.set_column('A:A', 18)
        worksheet.set_column('B:B', 45)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 18, money_format)
        worksheet.set_column('E:E', 18)

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name='itens_cadastrados.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ------------------------
# Exportar somente itens críticos (mínimo)
# ------------------------
@bp.route('/exportar_criticos')
@login_required
def exportar_criticos():

    from flask import send_file
    import pandas as pd
    import io
    from datetime import datetime

    tipo_servico_id = request.args.get(
        "tipo_servico_id",
        type=int
    )

    categoria = request.args.get(
        "categoria",
        ""
    ).strip().upper()

    alertas = buscar_alertas_estoque(
        tipo_servico_id
    )

    dados = []

    for estoque, item, tipo_servico in alertas:

        if categoria and (item.categoria or "").upper() != categoria:
            continue

        dados.append({
            "Código": item.codigo,
            "Descrição": item.descricao,
            "Unidade": item.unidade,
            "Categoria": item.categoria or "MATERIAL",
            "Tipo Serviço": tipo_servico.nome if tipo_servico else "-",
            "Quantidade Atual": estoque.quantidade or 0,
            "Estoque Mínimo": estoque.quantidade_minima or 0
        })

    df = pd.DataFrame(
        dados,
        columns=[
            "Código",
            "Descrição",
            "Unidade",
            "Categoria",
            "Tipo Serviço",
            "Quantidade Atual",
            "Estoque Mínimo"
        ]
    )

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:

        workbook = writer.book

        worksheet = workbook.add_worksheet('Alerta Pedido')
        writer.sheets['Alerta Pedido'] = worksheet

        titulo_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'font_color': 'white',
            'bg_color': '#002B55',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        subtitulo_format = workbook.add_format({
            'italic': True,
            'font_color': '#4B5563',
            'align': 'center',
            'valign': 'vcenter'
        })

        header_format = workbook.add_format({
            'bold': True,
            'font_color': 'white',
            'bg_color': '#002B55',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        normal_format = workbook.add_format({
            'border': 1,
            'valign': 'vcenter'
        })

        center_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        qtd_alerta_format = workbook.add_format({
            'bold': True,
            'bg_color': '#F8D7DA',
            'font_color': '#842029',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        minimo_alerta_format = workbook.add_format({
            'bold': True,
            'bg_color': '#DC3545',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        worksheet.merge_range(
            'A1:G1',
            'RELATÓRIO DE ALERTA DE PEDIDO - ITENS CRÍTICOS',
            titulo_format
        )

        worksheet.merge_range(
            'A2:G2',
            f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}',
            subtitulo_format
        )

        linha_header = 3

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(
                linha_header,
                col_num,
                value,
                header_format
            )

        for row_num, item_linha in enumerate(dados, start=linha_header + 1):

            worksheet.write(row_num, 0, item_linha["Código"], center_format)
            worksheet.write(row_num, 1, item_linha["Descrição"], normal_format)
            worksheet.write(row_num, 2, item_linha["Unidade"], center_format)
            worksheet.write(row_num, 3, item_linha["Categoria"], center_format)
            worksheet.write(row_num, 4, item_linha["Tipo Serviço"], normal_format)
            worksheet.write(row_num, 5, item_linha["Quantidade Atual"], qtd_alerta_format)
            worksheet.write(row_num, 6, item_linha["Estoque Mínimo"], minimo_alerta_format)

        worksheet.set_column('A:A', 14)
        worksheet.set_column('B:B', 48)
        worksheet.set_column('C:C', 12)
        worksheet.set_column('D:D', 16)
        worksheet.set_column('E:E', 24)
        worksheet.set_column('F:F', 18)
        worksheet.set_column('G:G', 18)

        worksheet.set_row(0, 26)
        worksheet.set_row(1, 20)
        worksheet.set_row(linha_header, 22)

        worksheet.freeze_panes(4, 0)

        worksheet.autofilter(
            linha_header,
            0,
            linha_header + len(dados),
            6
        )

    output.seek(0)

    data_arquivo = datetime.now().strftime(
        "%Y-%m-%d_%H-%M"
    )

    return send_file(
        output,
        as_attachment=True,
        download_name=f'alerta_pedido_estoque_{data_arquivo}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
# ------------------------
# Exportar Alertas de Estoque em Excel
# ------------------------
@bp.route('/alertas/exportar_excel')
@login_required
def exportar_alertas_excel():
    from flask import send_file
    import pandas as pd
    import io
    from datetime import datetime

    tipo_servico_id = request.args.get("tipo_servico", type=int)
    alertas = buscar_alertas_estoque(tipo_servico_id)

    dados = []

    for estoque, item, tipo_servico in alertas:
        dados.append({
            "Código": item.codigo,
            "Descrição": item.descricao,
            "Unidade": item.unidade,
            "Categoria": item.categoria or "MATERIAL",
            "Tipo Serviço": tipo_servico.nome if tipo_servico else "-",
            "Quantidade Atual": estoque.quantidade or 0,
            "Estoque Mínimo": estoque.quantidade_minima or 0
        })

    df = pd.DataFrame(
        dados,
        columns=[
            "Código",
            "Descrição",
            "Unidade",
            "Categoria",
            "Tipo Serviço",
            "Quantidade Atual",
            "Estoque Mínimo"
        ]
    )

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet('Estoque Baixo')
        writer.sheets['Estoque Baixo'] = worksheet

        titulo_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'font_color': 'white',
            'bg_color': '#002B55',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        subtitulo_format = workbook.add_format({
            'italic': True,
            'font_color': '#4B5563',
            'align': 'center',
            'valign': 'vcenter'
        })

        header_format = workbook.add_format({
            'bold': True,
            'font_color': 'white',
            'bg_color': '#002B55',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        normal_format = workbook.add_format({
            'border': 1,
            'valign': 'vcenter'
        })

        center_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        qtd_alerta_format = workbook.add_format({
            'bold': True,
            'bg_color': '#F8D7DA',
            'font_color': '#842029',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        minimo_alerta_format = workbook.add_format({
            'bold': True,
            'bg_color': '#DC3545',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        worksheet.merge_range(
            'A1:G1',
            'RELATÓRIO DE ESTOQUE BAIXO - ITENS CRÍTICOS',
            titulo_format
        )

        worksheet.merge_range(
            'A2:G2',
            f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}',
            subtitulo_format
        )

        linha_header = 3

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(linha_header, col_num, value, header_format)

        for row_num, item_linha in enumerate(dados, start=linha_header + 1):
            worksheet.write(row_num, 0, item_linha["Código"], center_format)
            worksheet.write(row_num, 1, item_linha["Descrição"], normal_format)
            worksheet.write(row_num, 2, item_linha["Unidade"], center_format)
            worksheet.write(row_num, 3, item_linha["Categoria"], center_format)
            worksheet.write(row_num, 4, item_linha["Tipo Serviço"], normal_format)
            worksheet.write(row_num, 5, item_linha["Quantidade Atual"], qtd_alerta_format)
            worksheet.write(row_num, 6, item_linha["Estoque Mínimo"], minimo_alerta_format)

        worksheet.set_column('A:A', 14)
        worksheet.set_column('B:B', 48)
        worksheet.set_column('C:C', 12)
        worksheet.set_column('D:D', 16)
        worksheet.set_column('E:E', 24)
        worksheet.set_column('F:F', 18)
        worksheet.set_column('G:G', 18)

        worksheet.set_row(0, 26)
        worksheet.set_row(1, 20)
        worksheet.set_row(linha_header, 22)

        worksheet.freeze_panes(4, 0)

        worksheet.autofilter(
            linha_header,
            0,
            linha_header + len(dados),
            6
        )

    output.seek(0)

    data_atual = datetime.now().strftime("%Y-%m-%d_%H-%M")

    return send_file(
        output,
        as_attachment=True,
        download_name=f'relatorio_estoque_baixo_{data_atual}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ------------------------
# Exportar Alertas de Estoque em PDF
# ------------------------
@bp.route('/alertas/exportar_pdf')
@login_required
def exportar_alertas_pdf():
    from flask import send_file
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import cm
    import io
    from datetime import datetime

    tipo_servico_id = request.args.get("tipo_servico", type=int)
    alertas = buscar_alertas_estoque(tipo_servico_id)

    output = io.BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm
    )

    elementos = []
    styles = getSampleStyleSheet()

    elementos.append(Paragraph("<b>Relatório de Estoque Baixo</b>", styles["Title"]))
    elementos.append(Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    elementos.append(Spacer(1, 12))

    dados = [[
        "Código",
        "Descrição",
        "Unidade",
        "Categoria",
        "Tipo Serviço",
        "Atual",
        "Mínimo",
        "Endereço",
        "Valor Unit.",
        "Total Atual"
    ]]

    for estoque, item, tipo_servico in alertas:
        quantidade_atual = estoque.quantidade or 0
        valor_unitario = float(item.valor or 0)
        valor_total = quantidade_atual * valor_unitario

        dados.append([
            item.codigo,
            item.descricao,
            item.unidade,
            item.categoria or "MATERIAL",
            tipo_servico.nome if tipo_servico else "-",
            str(quantidade_atual),
            str(estoque.quantidade_minima or 0),
            estoque.endereco or "-",
            f"R$ {valor_unitario:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ])

    if len(dados) == 1:
        dados.append(["-", "Nenhum item em estoque baixo encontrado", "-", "-", "-", "-", "-", "-", "-", "-"])

    tabela = Table(
        dados,
        colWidths=[
            2.0 * cm,
            5.5 * cm,
            1.8 * cm,
            2.4 * cm,
            3.8 * cm,
            1.6 * cm,
            1.6 * cm,
            3.8 * cm,
            2.3 * cm,
            2.3 * cm
        ]
    )

    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#002B55")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (5, 1), (6, -1), 'CENTER'),
        ('ALIGN', (8, 1), (9, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")]),
    ]))

    elementos.append(tabela)
    doc.build(elementos)

    output.seek(0)

    data_arquivo = datetime.now().strftime("%Y-%m-%d_%H-%M")

    return send_file(
        output,
        as_attachment=True,
        download_name=f'relatorio_estoque_baixo_{data_arquivo}.pdf',
        mimetype='application/pdf'
    )
    
@bp.route('/exportar_saldo_excel')
@login_required
def exportar_saldo_excel():
    from flask import send_file
    import pandas as pd
    import io
    from datetime import datetime
    from sqlalchemy import func
    from app.models import Empresa, TipoServico

    tipo_estoque = request.args.get("tipo_estoque")
    cliente_id = request.args.get("cliente_id", type=int)
    tipo_servico_id = request.args.get("tipo_servico_id", type=int)
    categoria = request.args.get("categoria", "").strip().upper()

    cliente_nome = "-"
    tipo_servico_nome = "Todos"

    if cliente_id:
        cliente = Empresa.query.get(cliente_id)
        cliente_nome = cliente.razao_social if cliente else "-"

    if tipo_servico_id:
        tipo_servico = TipoServico.query.get(tipo_servico_id)
        tipo_servico_nome = tipo_servico.nome if tipo_servico else "Todos"

    query = db.session.query(
        Item.codigo,
        Item.descricao,
        Item.unidade,
        Item.valor,
        func.sum(Estoque.quantidade).label("quantidade"),
        func.max(Estoque.quantidade_minima).label("quantidade_minima"),
        func.max(Estoque.endereco).label("endereco")
    ).join(
        Item,
        Estoque.item_id == Item.id
    )

    if categoria:
        query = query.filter(Item.categoria == categoria)

    if tipo_estoque == "empresa":
        query = query.filter(
            db.or_(
                Estoque.tipo_estoque == "empresa",
                Estoque.tipo_estoque == None
            )
        )

    elif tipo_estoque == "cliente":
        query = query.filter(Estoque.tipo_estoque == "cliente")

        if cliente_id:
            query = query.filter(Estoque.cliente_id == cliente_id)

    if tipo_servico_id:
        query = query.filter(Estoque.tipo_servico_id == tipo_servico_id)

    resultados = query.group_by(
        Estoque.item_id,
        Item.codigo,
        Item.descricao,
        Item.unidade,
        Item.valor
    ).having(
        func.sum(Estoque.quantidade) > 0
    ).order_by(
        Item.descricao
    ).all()

    dados = []

    for r in resultados:
        dados.append({
            "Código": r.codigo,
            "Descrição": r.descricao,
            "Unidade": r.unidade,
            "Valor (R$)": float(r.valor or 0),
            "Quantidade": r.quantidade or 0,
            "Estoque Mínimo": r.quantidade_minima or "",
            "Endereço": r.endereco or ""
        })

    df = pd.DataFrame(dados)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet("Saldo Estoque")
        writer.sheets["Saldo Estoque"] = worksheet

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

        money_format = workbook.add_format({
            "border": 1,
            "num_format": 'R$ #,##0.00',
            "valign": "vcenter"
        })

        qtd_alerta_format = workbook.add_format({
            "bold": True,
            "bg_color": "#F8D7DA",
            "font_color": "#842029",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        worksheet.merge_range("A1:G1", "RELATÓRIO DE SALDO DE ESTOQUE", titulo_format)

        worksheet.write("A3", "Tipo de Estoque:", info_format)
        worksheet.write(
            "B3",
            "EMPRESA" if tipo_estoque == "empresa" else "CLIENTE",
            normal_format
        )

        worksheet.write("D3", "Cliente:", info_format)
        worksheet.write(
            "E3",
            cliente_nome if cliente_id else "TODOS",
            normal_format
        )

        worksheet.write("A4", "Tipo de Serviço:", info_format)
        worksheet.write("B4", tipo_servico_nome, normal_format)

        worksheet.write("D4", "Categoria:", info_format)
        worksheet.write("E4", categoria or "Todas", normal_format)

        worksheet.write("A5", "Gerado em:", info_format)
        worksheet.write("B5", datetime.now().strftime("%d/%m/%Y %H:%M"), normal_format)

        linha_header = 7

        for col_num, coluna in enumerate(df.columns):
            worksheet.write(linha_header, col_num, coluna, header_format)

        for row_num, item in enumerate(dados, start=linha_header + 1):
            worksheet.write(row_num, 0, item["Código"], center_format)
            worksheet.write(row_num, 1, item["Descrição"], normal_format)
            worksheet.write(row_num, 2, item["Unidade"], center_format)
            worksheet.write(row_num, 3, item["Valor (R$)"], money_format)

            minimo = item["Estoque Mínimo"] or 0
            quantidade = item["Quantidade"] or 0

            if minimo and quantidade <= minimo:
                worksheet.write(row_num, 4, quantidade, qtd_alerta_format)
            else:
                worksheet.write(row_num, 4, quantidade, center_format)

            worksheet.write(row_num, 5, item["Estoque Mínimo"], center_format)
            worksheet.write(row_num, 6, item["Endereço"], normal_format)

        worksheet.set_column("A:A", 14)
        worksheet.set_column("B:B", 45)
        worksheet.set_column("C:C", 12)
        worksheet.set_column("D:D", 16)
        worksheet.set_column("E:E", 14)
        worksheet.set_column("F:F", 18)
        worksheet.set_column("G:G", 42)

        worksheet.set_row(0, 26)
        worksheet.set_row(linha_header, 22)

        worksheet.freeze_panes(linha_header + 1, 0)
        worksheet.autofilter(linha_header, 0, linha_header + len(dados), len(df.columns) - 1)

    output.seek(0)

    data_arquivo = datetime.now().strftime("%Y-%m-%d_%H-%M")

    return send_file(
        output,
        as_attachment=True,
        download_name=f"saldo_estoque_{data_arquivo}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )