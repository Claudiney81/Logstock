from flask import Blueprint, render_template, request, send_file
from sqlalchemy import func
from app.models import Tecnico, SaldoTecnico, TipoServico, Item, Empresa
from app.extensions import db
import pandas as pd
import io

try:
    from app.models import OrdemServico
except Exception:
    OrdemServico = None


bp = Blueprint('saldo_tecnico', __name__)


@bp.route('/saldo_tecnico')
def exibir_saldo():
    termo_busca = request.args.get('tecnico', '').strip()

    query = Tecnico.query.filter(
        Tecnico.status == 'Ativo',
        Tecnico.funcao == 'Instalador'
    )

    if termo_busca:
        query = query.filter(Tecnico.nome.ilike(f'%{termo_busca}%'))

    tecnicos = query.order_by(Tecnico.nome).all()

    return render_template(
        'saldo_tecnico.html',
        tecnicos=tecnicos,
        termo_busca=termo_busca
    )


@bp.route('/saldo_tecnico/<int:id_tecnico>', methods=['GET'])
def saldo_detalhado(id_tecnico):
    tecnico = Tecnico.query.get_or_404(id_tecnico)

    tipo_servico_id = request.args.get('tipo_servico_id', 'todos')
    tipo_estoque = request.args.get('tipo_estoque', 'todos')
    cliente_id = request.args.get('cliente_id', type=int)
    ordem_servico_id = request.args.get('ordem_servico_id', type=int)

    cliente_selecionado = Empresa.query.get(cliente_id) if cliente_id else None

    campos_query = [
        Item.codigo.label('codigo'),
        Item.descricao.label('descricao'),
        Item.unidade.label('unidade'),
        SaldoTecnico.cliente_id.label('cliente_id'),
        Empresa.razao_social.label('cliente_nome'),
        SaldoTecnico.ordem_servico_id.label('ordem_servico_id'),
        SaldoTecnico.endereco.label('endereco'),
        func.coalesce(
            func.max(SaldoTecnico.valor_unitario),
            Item.valor
        ).label('valor_unitario'),
        func.sum(SaldoTecnico.quantidade).label('quantidade'),
        func.max(SaldoTecnico.quantidade_minima).label('quantidade_minima')
    ]

    if OrdemServico:
        campos_query.append(OrdemServico.numero_os.label('numero_os'))

    query = (
        db.session.query(*campos_query)
        .join(Item, Item.id == SaldoTecnico.item_id)
        .outerjoin(Empresa, Empresa.id == SaldoTecnico.cliente_id)
        .filter(SaldoTecnico.tecnico_id == id_tecnico)
        .filter(SaldoTecnico.quantidade > 0)
        .filter(
            ~func.lower(Item.categoria).in_([
                'ferramenta',
                'epi'
            ])
        )
    )

    if OrdemServico:
        query = query.outerjoin(
            OrdemServico,
            OrdemServico.id == SaldoTecnico.ordem_servico_id
        )

    if tipo_servico_id != 'todos':
        tipo_servico_consulta = 1

        query = query.filter(
            SaldoTecnico.tipo_servico_id == tipo_servico_consulta
        )

    if tipo_estoque == 'cliente':
        query = query.filter(
            SaldoTecnico.tipo_estoque == 'cliente',
            SaldoTecnico.cliente_id.isnot(None),
            SaldoTecnico.ordem_servico_id.isnot(None)
        )

    elif tipo_estoque == 'empresa':
        query = query.filter(
            SaldoTecnico.tipo_estoque == 'empresa',
            SaldoTecnico.cliente_id.is_(None),
            SaldoTecnico.ordem_servico_id.is_(None)
        )

    if cliente_id:
        query = query.filter(
            SaldoTecnico.cliente_id == cliente_id
        )

    if ordem_servico_id:
        query = query.filter(
            SaldoTecnico.ordem_servico_id == ordem_servico_id
        )

    if tipo_estoque == 'empresa':
        group_by_campos = [
            Item.id,
            Item.codigo,
            Item.descricao,
            Item.unidade,
            Item.valor
        ]
    else:
        group_by_campos = [
            Item.id,
            Item.codigo,
            Item.descricao,
            Item.unidade,
            SaldoTecnico.cliente_id,
            Empresa.razao_social,
            SaldoTecnico.ordem_servico_id,
            SaldoTecnico.endereco,
            Item.valor
        ]

        if OrdemServico:
            group_by_campos.append(OrdemServico.numero_os)

    saldos = (
        query
        .group_by(*group_by_campos)
        .order_by(
            Item.descricao
        )
        .all()
    )

    tipos_servico = TipoServico.query.order_by(TipoServico.nome).all()

    clientes = (
        db.session.query(Empresa)
        .join(
            SaldoTecnico,
            SaldoTecnico.cliente_id == Empresa.id
        )
        .filter(SaldoTecnico.tecnico_id == id_tecnico)
        .filter(SaldoTecnico.cliente_id.isnot(None))
        .filter(SaldoTecnico.quantidade > 0)
        .filter(Empresa.razao_social.notilike('%CCM%'))
        .distinct()
        .order_by(Empresa.razao_social)
        .all()
    )

    ordens_servico = []

    if OrdemServico and cliente_id and tipo_estoque == 'cliente':
        ordens_servico = (
            db.session.query(OrdemServico)
            .join(SaldoTecnico, SaldoTecnico.ordem_servico_id == OrdemServico.id)
            .filter(SaldoTecnico.tecnico_id == id_tecnico)
            .filter(SaldoTecnico.tipo_estoque == 'cliente')
            .filter(SaldoTecnico.cliente_id == cliente_id)
            .filter(SaldoTecnico.ordem_servico_id.isnot(None))
            .filter(SaldoTecnico.quantidade > 0)
            .distinct()
            .order_by(OrdemServico.numero_os)
            .all()
        )

    return render_template(
        'saldo_tecnico_detalhado.html',
        tecnico=tecnico,
        saldos=saldos,
        tipos_servico=tipos_servico,
        clientes=clientes,
        ordens_servico=ordens_servico,
        tipo_servico_id=tipo_servico_id,
        tipo_estoque=tipo_estoque,
        cliente_id=cliente_id,
        ordem_servico_id=ordem_servico_id,
        cliente_selecionado=cliente_selecionado
    )


@bp.route('/saldo_tecnico/<int:id_tecnico>/exportar')
def exportar_saldo_tecnico(id_tecnico):
    tecnico = Tecnico.query.get_or_404(id_tecnico)

    tipo_servico_id = request.args.get('tipo_servico_id', 'todos')
    tipo_estoque = request.args.get('tipo_estoque', 'todos')
    cliente_id = request.args.get('cliente_id', type=int)
    ordem_servico_id = request.args.get('ordem_servico_id', type=int)

    campos_query = [
        Item.codigo.label('Código'),
        Item.descricao.label('Descrição'),
        Item.unidade.label('Unidade'),
        Empresa.razao_social.label('Cliente'),
        SaldoTecnico.ordem_servico_id.label('ordem_servico_id'),
        SaldoTecnico.endereco.label('Endereço'),
        func.coalesce(
            func.max(SaldoTecnico.valor_unitario),
            Item.valor
        ).label('Valor Unitário'),
        func.sum(SaldoTecnico.quantidade).label('Saldo Atual'),
        func.max(SaldoTecnico.quantidade_minima).label('Quantidade Mínima')
    ]

    if OrdemServico:
        campos_query.append(OrdemServico.numero_os.label('O.S'))

    query = (
        db.session.query(*campos_query)
        .join(Item, Item.id == SaldoTecnico.item_id)
        .outerjoin(Empresa, Empresa.id == SaldoTecnico.cliente_id)
        .filter(SaldoTecnico.tecnico_id == id_tecnico)
        .filter(SaldoTecnico.quantidade > 0)
        .filter(~func.lower(Item.categoria).in_(['ferramenta', 'epi']))
    )

    if OrdemServico:
        query = query.outerjoin(
            OrdemServico,
            OrdemServico.id == SaldoTecnico.ordem_servico_id
        )

    if tipo_servico_id != 'todos':
        tipo_servico_consulta = 1

        query = query.filter(
            SaldoTecnico.tipo_servico_id == tipo_servico_consulta
        )

    if tipo_estoque == 'cliente':
        query = query.filter(
            SaldoTecnico.tipo_estoque == 'cliente',
            SaldoTecnico.cliente_id.isnot(None),
            SaldoTecnico.ordem_servico_id.isnot(None)
        )

    elif tipo_estoque == 'empresa':
        query = query.filter(
            SaldoTecnico.tipo_estoque == 'empresa',
            SaldoTecnico.cliente_id.is_(None),
            SaldoTecnico.ordem_servico_id.is_(None)
        )

    if cliente_id:
        query = query.filter(
            SaldoTecnico.cliente_id == cliente_id
        )

    if ordem_servico_id:
        query = query.filter(
            SaldoTecnico.ordem_servico_id == ordem_servico_id
        )

    if tipo_estoque == 'empresa':
        group_by_campos = [
            Item.id,
            Item.codigo,
            Item.descricao,
            Item.unidade,
            Item.valor
        ]
    else:
        group_by_campos = [
            Item.id,
            Item.codigo,
            Item.descricao,
            Item.unidade,
            Empresa.razao_social,
            SaldoTecnico.ordem_servico_id,
            SaldoTecnico.endereco,
            Item.valor
        ]

        if OrdemServico:
            group_by_campos.append(OrdemServico.numero_os)

    saldos = (
        query
        .group_by(*group_by_campos)
        .order_by(Item.descricao)
        .all()
    )

    dados = []

    for row in saldos:
        row_dict = row._asdict()

        saldo = row_dict.get('Saldo Atual') or 0
        minimo = row_dict.get('Quantidade Mínima') or 0
        necessidade = max(minimo - saldo, 0)

        linha = {}

        if tipo_estoque == 'cliente':
            linha['Cliente'] = row_dict.get('Cliente') or ''
            linha['O.S'] = row_dict.get('O.S') or ''
            linha['Endereço'] = row_dict.get('Endereço') or ''

        linha.update({
            'Código': row_dict.get('Código'),
            'Descrição': row_dict.get('Descrição'),
            'Unidade': row_dict.get('Unidade'),
            'Valor Unitário': float(row_dict.get('Valor Unitário') or 0),
            'Saldo Atual': saldo,
            'Quantidade Mínima': minimo,
            'Necessidade Reposição': necessidade
        })

        dados.append(linha)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df = pd.DataFrame(dados)

        if df.empty:
            if tipo_estoque == 'cliente':
                df = pd.DataFrame(columns=[
                    'Cliente',
                    'O.S',
                    'Endereço',
                    'Código',
                    'Descrição',
                    'Unidade',
                    'Valor Unitário',
                    'Saldo Atual',
                    'Quantidade Mínima',
                    'Necessidade Reposição'
                ])
            else:
                df = pd.DataFrame(columns=[
                    'Código',
                    'Descrição',
                    'Unidade',
                    'Valor Unitário',
                    'Saldo Atual',
                    'Quantidade Mínima',
                    'Necessidade Reposição'
                ])

        df.to_excel(
            writer,
            startrow=7,
            index=False,
            sheet_name='Saldo Técnico'
        )

        workbook = writer.book
        worksheet = writer.sheets['Saldo Técnico']

        titulo = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#002b55',
            'font_color': 'white',
            'border': 1
        })

        info_label = workbook.add_format({
            'bold': True,
            'bg_color': '#EAF2FB',
            'font_color': '#002b55',
            'border': 1
        })

        info_valor = workbook.add_format({
            'border': 1
        })

        cabecalho = workbook.add_format({
            'bold': True,
            'bg_color': '#DCE6F1',
            'font_color': '#000000',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        texto = workbook.add_format({
            'border': 1,
            'valign': 'vcenter'
        })

        centro = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        numero = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': '0'
        })

        qtd_alerta = workbook.add_format({
            'border': 1,
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#F8D7DA',
            'font_color': '#842029',
            'num_format': '0'
        })

        ultima_coluna = len(df.columns) - 1

        worksheet.merge_range(
            0,
            0,
            0,
            ultima_coluna,
            f'RELATÓRIO DE SALDO TÉCNICO - {tecnico.nome}',
            titulo
        )

        worksheet.write(2, 0, 'Técnico:', info_label)
        worksheet.write(2, 1, tecnico.nome, info_valor)

        worksheet.write(2, 3, 'Tipo de Estoque:', info_label)
        worksheet.write(
            2,
            4,
            'Cliente' if tipo_estoque == 'cliente' else 'Empresa',
            info_valor
        )

        worksheet.write(3, 0, 'Total de Itens:', info_label)
        worksheet.write(3, 1, len(df), info_valor)

        worksheet.write(3, 3, 'Gerado em:', info_label)
        worksheet.write(3, 4, pd.Timestamp.now().strftime('%d/%m/%Y %H:%M'), info_valor)

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(7, col_num, value, cabecalho)

        for row_num, item in enumerate(dados, start=8):
            for col_num, coluna in enumerate(df.columns):
                valor = item.get(coluna, '')

                if coluna == 'Valor Unitário':
                    worksheet.write(row_num, col_num, valor, workbook.add_format({
                        'border': 1,
                        'align': 'right',
                        'valign': 'vcenter',
                        'num_format': 'R$ #,##0.00'
                    }))
                elif coluna in ['Saldo Atual', 'Quantidade Mínima', 'Necessidade Reposição']:
                    if coluna == 'Necessidade Reposição' and valor > 0:
                        worksheet.write(row_num, col_num, valor, qtd_alerta)
                    else:
                        worksheet.write(row_num, col_num, valor, numero)
                elif coluna in ['Código', 'Unidade']:
                    worksheet.write(row_num, col_num, valor, centro)
                else:
                    worksheet.write(row_num, col_num, valor, texto)

        worksheet.set_column(0, ultima_coluna, 20)
        worksheet.set_column('B:B', 45)

        worksheet.set_row(0, 26)
        worksheet.set_row(7, 22)

        worksheet.freeze_panes(8, 0)

        worksheet.autofilter(
            7,
            0,
            7 + len(df),
            ultima_coluna
        )

    output.seek(0)

    nome_arquivo = f"saldo_tecnico_{tecnico.nome.replace(' ', '_')}.xlsx"

    return send_file(
        output,
        download_name=nome_arquivo,
        as_attachment=True
    )
