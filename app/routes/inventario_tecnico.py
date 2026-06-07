from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from datetime import datetime
from sqlalchemy import func
from types import SimpleNamespace
import pandas as pd
import io

from app.models import (
    Tecnico,
    TipoServico,
    Item,
    InventarioTecnico,
    InventarioTecnicoItem,
    SaldoTecnico,
    Estoque,
    Empresa,
    EquipamentoTecnico
)
from app.extensions import db


bp_inventario = Blueprint(
    'inventario_tecnico',
    __name__,
    url_prefix='/inventario_tecnico'
)


def _filtrar_saldo_empresa_geral(query):
    """
    Para estoque empresa no inventário técnico, considera somente saldo geral do técnico.
    Evita misturar saldos de cliente/O.S. que por algum motivo estejam marcados como empresa.
    """
    query = query.filter(SaldoTecnico.cliente_id.is_(None))

    if hasattr(SaldoTecnico, 'ordem_servico_id'):
        query = query.filter(SaldoTecnico.ordem_servico_id.is_(None))

    return query


def buscar_saldo_tecnico(tecnico_id, tipo_estoque, categoria, tipo_servico_id=None, cliente_id=None):

    if not tecnico_id:
        return []

    categoria = (categoria or '').strip().upper()

    # ==================================================
    # FERRAMENTAS E EPIs
    # Vêm da tabela EquipamentoTecnico
    # ==================================================
    if categoria in ['FERRAMENTA', 'EPI']:

        return (
            db.session.query(
                Item.id.label('item_id'),
                Item.codigo.label('codigo'),
                Item.descricao.label('descricao'),
                Item.unidade.label('unidade'),
                Item.categoria.label('categoria'),
                func.sum(EquipamentoTecnico.quantidade).label('quantidade')
            )
            .join(Item, Item.id == EquipamentoTecnico.item_id)
            .filter(
                EquipamentoTecnico.tecnico_id == tecnico_id,
                EquipamentoTecnico.status == 'tecnico',
                func.upper(Item.categoria) == categoria,
                EquipamentoTecnico.quantidade > 0
            )
            .group_by(
                Item.id,
                Item.codigo,
                Item.descricao,
                Item.unidade,
                Item.categoria
            )
            .order_by(Item.descricao)
            .all()
        )

    # ==================================================
    # MATERIAIS
    # Vêm da tabela SaldoTecnico
    # ==================================================
    if not tipo_estoque:
        return []

    query_saldo = (
        db.session.query(
            Item.id.label('item_id'),
            Item.codigo.label('codigo'),
            Item.descricao.label('descricao'),
            Item.unidade.label('unidade'),
            Item.categoria.label('categoria'),
            func.sum(SaldoTecnico.quantidade).label('quantidade')
        )
        .join(Item, Item.id == SaldoTecnico.item_id)
        .filter(
            SaldoTecnico.tecnico_id == tecnico_id,
            SaldoTecnico.tipo_estoque == tipo_estoque,
            SaldoTecnico.quantidade > 0,
            func.upper(Item.categoria) == categoria
        )
    )

    if categoria == 'MATERIAL' and tipo_servico_id:
        query_saldo = query_saldo.filter(
            SaldoTecnico.tipo_servico_id == tipo_servico_id
        )

    if tipo_estoque == 'empresa':
        query_saldo = _filtrar_saldo_empresa_geral(query_saldo)

    if tipo_estoque == 'cliente':
        if cliente_id:
            query_saldo = query_saldo.filter(
                SaldoTecnico.cliente_id == cliente_id
            )
        else:
            return []

    return (
        query_saldo
        .group_by(
            Item.id,
            Item.codigo,
            Item.descricao,
            Item.unidade,
            Item.categoria
        )
        .order_by(Item.descricao)
        .all()
    )


# ========== NOVO INVENTÁRIO ==========
@bp_inventario.route('/novo', methods=['GET', 'POST'])
def registrar_inventario():

    tecnicos = (
        Tecnico.query
        .filter(Tecnico.status == 'Ativo')
        .order_by(Tecnico.nome)
        .all()
    )

    tipos_servico = (
        TipoServico.query
        .order_by(TipoServico.nome.asc())
        .all()
    )

    tecnico_id = request.values.get('tecnico_id', type=int)
    tipo_estoque = request.values.get('tipo_estoque', '')
    tipo_servico_id = request.values.get('tipo_servico_id', type=int)
    cliente_id = request.values.get('cliente_id', type=int)
    responsavel = request.values.get('responsavel', '')

    categoria = request.values.get('categoria', 'MATERIAL').strip().upper()

    if categoria not in ['MATERIAL', 'FERRAMENTA', 'EPI']:
        categoria = 'MATERIAL'

    clientes = []

    if tecnico_id:
            clientes = (
            db.session.query(Empresa)
            .join(SaldoTecnico, SaldoTecnico.cliente_id == Empresa.id)
            .filter(SaldoTecnico.tecnico_id == tecnico_id)
            .filter(SaldoTecnico.tipo_estoque == 'cliente')
            .filter(func.lower(Empresa.tipo_empresa) == 'cliente')
            .distinct()
            .order_by(Empresa.razao_social)
            .all()
        )
    saldo_tecnico = buscar_saldo_tecnico(
        tecnico_id=tecnico_id,
        tipo_estoque=tipo_estoque,
        categoria=categoria,
        tipo_servico_id=tipo_servico_id,
        cliente_id=cliente_id
    )

    if request.method == 'POST' and request.form.get('acao') == 'registrar':

        if not tecnico_id:
            flash('Selecione o técnico.', 'warning')
            return redirect(url_for('inventario_tecnico.registrar_inventario'))

        if not tipo_estoque:
            flash('Selecione o tipo de estoque.', 'warning')
            return redirect(url_for('inventario_tecnico.registrar_inventario'))

        if categoria == 'MATERIAL' and not tipo_servico_id:
            flash('Selecione o tipo de serviço.', 'warning')
            return redirect(url_for(
                'inventario_tecnico.registrar_inventario',
                tecnico_id=tecnico_id,
                tipo_estoque=tipo_estoque,
                tipo_servico_id=tipo_servico_id,
                cliente_id=cliente_id,
                responsavel=responsavel,
                categoria=categoria
            ))

        if tipo_estoque == 'cliente' and not cliente_id:
            flash('Selecione o cliente.', 'warning')
            return redirect(url_for(
                'inventario_tecnico.registrar_inventario',
                tecnico_id=tecnico_id,
                tipo_estoque=tipo_estoque,
                tipo_servico_id=tipo_servico_id,
                responsavel=responsavel,
                categoria=categoria
            ))

        codigos = request.form.getlist('codigo[]')
        quantidades = request.form.getlist('quantidade_contada[]')

        itens_preenchidos = [q for q in quantidades if q and q.strip() != '']

        if not itens_preenchidos:
            flash('Nenhum item informado para contagem.', 'warning')
            return redirect(url_for(
                'inventario_tecnico.registrar_inventario',
                tecnico_id=tecnico_id,
                tipo_estoque=tipo_estoque,
                tipo_servico_id=tipo_servico_id,
                cliente_id=cliente_id,
                responsavel=responsavel,
                categoria=categoria
            ))

        inventario = InventarioTecnico(
            tecnico_id=tecnico_id,
            tipo_servico_id=tipo_servico_id if tipo_servico_id else None,
            data=datetime.utcnow(),
            responsavel=responsavel
        )

        db.session.add(inventario)
        db.session.flush()

        for i, codigo in enumerate(codigos):

            if i >= len(quantidades):
                continue

            if not quantidades[i] or not quantidades[i].strip():
                continue

            item = Item.query.filter_by(codigo=codigo).first()

            if not item:
                continue

            quantidade_contada = int(quantidades[i])
            categoria_item = (item.categoria or categoria or '').strip().upper()

            # ==================================================
            # FERRAMENTA / EPI
            # Usa EquipamentoTecnico
            # ==================================================
            if categoria_item in ['FERRAMENTA', 'EPI']:

                quantidade_existente = (
                    db.session.query(func.sum(EquipamentoTecnico.quantidade))
                    .filter(
                        EquipamentoTecnico.tecnico_id == tecnico_id,
                        EquipamentoTecnico.item_id == item.id,
                        EquipamentoTecnico.status == 'tecnico'
                    )
                    .scalar()
                    or 0
                )

                db.session.add(InventarioTecnicoItem(
                    inventario_id=inventario.id,
                    item_id=item.id,
                    quantidade_existente=quantidade_existente,
                    quantidade_contada=quantidade_contada
                ))
            
                # Inventário apenas registra a conferência.
                # Não altera saldo de Ferramenta/EPI automaticamente.
                continue
            # ==================================================
            # MATERIAL
            # Usa SaldoTecnico
            # ==================================================
            quantidade_existente_query = (
                db.session.query(func.sum(SaldoTecnico.quantidade))
                .filter(
                    SaldoTecnico.tecnico_id == tecnico_id,
                    SaldoTecnico.item_id == item.id,
                    SaldoTecnico.tipo_estoque == tipo_estoque
                )
            )

            if categoria == 'MATERIAL' and tipo_servico_id:
                quantidade_existente_query = quantidade_existente_query.filter(
                    SaldoTecnico.tipo_servico_id == tipo_servico_id
                )

            if tipo_estoque == 'empresa':
                quantidade_existente_query = _filtrar_saldo_empresa_geral(
                    quantidade_existente_query
                )

            if tipo_estoque == 'cliente' and cliente_id:
                quantidade_existente_query = quantidade_existente_query.filter(
                    SaldoTecnico.cliente_id == cliente_id
                )

            quantidade_existente = quantidade_existente_query.scalar() or 0

            db.session.add(InventarioTecnicoItem(
                inventario_id=inventario.id,
                item_id=item.id,
                quantidade_existente=quantidade_existente,
                quantidade_contada=quantidade_contada
            ))
            
        db.session.commit()

        flash('Inventário registrado com sucesso.', 'success')
        return redirect(url_for('inventario_tecnico.historico_inventarios'))

    return render_template(
        'inventario_tecnico/novo.html',
        tecnicos=tecnicos,
        tipos_servico=tipos_servico,
        clientes=clientes,
        tecnico_id=tecnico_id,
        tipo_estoque=tipo_estoque,
        tipo_servico_id=tipo_servico_id,
        cliente_id=cliente_id,
        responsavel=responsavel,
        saldo_tecnico=saldo_tecnico,
        categoria=categoria
    )


# ========== FORMULÁRIO DE CONTAGEM SEM SALVAR ==========
@bp_inventario.route('/formulario_contagem')
def formulario_contagem():

    tecnico_id = request.args.get('tecnico_id', type=int)
    tipo_estoque = request.args.get('tipo_estoque', '')
    tipo_servico_id = request.args.get('tipo_servico_id', type=int)
    cliente_id = request.args.get('cliente_id', type=int)
    responsavel = request.args.get('responsavel', '')
    categoria = request.args.get('categoria', 'MATERIAL').strip().upper()

    tecnico = Tecnico.query.get(tecnico_id) if tecnico_id else None
    tipo_servico = TipoServico.query.get(tipo_servico_id) if tipo_servico_id else None

    saldo_tecnico = buscar_saldo_tecnico(
        tecnico_id=tecnico_id,
        tipo_estoque=tipo_estoque,
        categoria=categoria,
        tipo_servico_id=tipo_servico_id,
        cliente_id=cliente_id
    )

    itens_virtual = []

    for s in saldo_tecnico:
        item_obj = SimpleNamespace(
            codigo=s.codigo,
            descricao=s.descricao,
            unidade=s.unidade,
            categoria=s.categoria
        )

        itens_virtual.append(SimpleNamespace(
            item=item_obj,
            quantidade_existente=s.quantidade,
            quantidade_contada=''
        ))

    inventario_virtual = SimpleNamespace(
        tecnico=tecnico,
        tipo_servico=tipo_servico,
        itens=itens_virtual,
        data=datetime.utcnow(),
        responsavel=responsavel or '---',
        formulario_sem_salvar=True
    )

    return render_template(
        'inventario_tecnico/formulario.html',
        inventario=inventario_virtual,
        modo_impressao=True
    )


# ========== HISTÓRICO ==========
@bp_inventario.route('/historico')
def historico_inventarios():

    inventarios = (
        InventarioTecnico.query
        .order_by(InventarioTecnico.data.desc())
        .all()
    )

    return render_template(
        'inventario_tecnico/historico.html',
        inventarios=inventarios
    )


# ========== DETALHES ==========
@bp_inventario.route('/detalhes/<int:id>')
def detalhes_inventario(id):

    inventario = InventarioTecnico.query.get_or_404(id)

    total_existente = 0
    total_contado = 0

    for item in inventario.itens:

        valor_unitario = (
            item.item.valor
            if item.item and item.item.valor
            else 0
        )

        qtd_existente = item.quantidade_existente or 0
        qtd_contada = item.quantidade_contada or 0

        total_existente += qtd_existente * valor_unitario
        total_contado += qtd_contada * valor_unitario

    diferenca_financeira = total_contado - total_existente

    return render_template(
        'inventario_tecnico/detalhes.html',
        inventario=inventario,
        total_existente=total_existente,
        total_contado=total_contado,
        diferenca_financeira=diferenca_financeira
    )


# ========== EXPORTAR ==========
@bp_inventario.route('/exportar/<int:id>')
def exportar_inventario(id):

    inventario = InventarioTecnico.query.get_or_404(id)

    dados = []

    for item in inventario.itens:

        quantidade_existente = item.quantidade_existente or 0
        quantidade_contada = item.quantidade_contada or 0
        diferenca = quantidade_contada - quantidade_existente

        dados.append({
            'Código': item.item.codigo,
            'Descrição': item.item.descricao,
            'Categoria': item.item.categoria or 'MATERIAL',
            'Unidade': item.item.unidade,
            'Quantidade Existente': quantidade_existente,
            'Quantidade Contada': quantidade_contada,
            'Diferença': diferenca
        })

    df = pd.DataFrame(dados)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:

        sheet_name = 'Inventário'

        df.to_excel(
            writer,
            sheet_name=sheet_name,
            index=False,
            startrow=8
        )

        workbook = writer.book
        worksheet = writer.sheets['Inventário']

        titulo = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })

        rotulo = workbook.add_format({
            'bold': True
        })

        worksheet.merge_range(
            'A1:G1',
            'DETALHES DO INVENTÁRIO TÉCNICO',
            titulo
        )

        tecnico = inventario.tecnico.nome if inventario.tecnico else '-'

        categoria = (
            inventario.itens[0].item.categoria
            if inventario.itens and inventario.itens[0].item
            else '-'
        )

        tipo_servico = (
            inventario.tipo_servico.nome
            if inventario.tipo_servico
            else 'Estoque Geral'
        )

        data_inventario = inventario.data.strftime('%d/%m/%Y %H:%M')

        worksheet.write('A3', 'Técnico:', rotulo)
        worksheet.write('B3', tecnico)

        worksheet.write('D3', 'Categoria:', rotulo)
        worksheet.write('E3', categoria)

        worksheet.write('A4', 'Tipo de Serviço:', rotulo)
        worksheet.write('B4', tipo_servico)

        worksheet.write('D4', 'Data:', rotulo)
        worksheet.write('E4', data_inventario)

        worksheet.write('A5', 'Responsável:', rotulo)
        worksheet.write('B5', inventario.responsavel or '-')

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#002b55',
            'font_color': 'white',
            'border': 1
        })

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(8, col_num, value, header_format)

        worksheet.set_column('A:A', 18)
        worksheet.set_column('B:B', 45)
        worksheet.set_column('C:C', 18)
        worksheet.set_column('D:D', 12)
        worksheet.set_column('E:G', 20)
        worksheet.freeze_panes(9, 0)

    output.seek(0)

    nome_tecnico = (
        inventario.tecnico.nome.replace(' ', '_')
        if inventario.tecnico
        else 'tecnico'
    )

    return send_file(
        output,
        download_name=f'inventario_tecnico_{nome_tecnico}.xlsx',
        as_attachment=True
    )


# ========== FORMULÁRIO DE IMPRESSÃO DE INVENTÁRIO JÁ REGISTRADO ==========
@bp_inventario.route('/formulario/<int:id>')
def formulario_inventario(id):

    inventario = InventarioTecnico.query.get_or_404(id)

    return render_template(
        'inventario_tecnico/formulario.html',
        inventario=inventario,
        modo_impressao=True
    )


@bp_inventario.route('/devolver_estoque/<int:id>', methods=['GET', 'POST'])
def devolver_estoque(id):

    inventario = InventarioTecnico.query.get_or_404(id)

    if request.method == 'POST':

        motivo = request.form.get('motivo', '').strip()
        observacao = request.form.get('observacao', '').strip()

        if not motivo:
            flash('Informe o motivo da devolução.', 'warning')
            return redirect(url_for('inventario_tecnico.devolver_estoque', id=id))

        houve_devolucao = False

        for item_inv in inventario.itens:

            qtd_devolver = request.form.get(
                f'qtd_devolver_{item_inv.item_id}',
                type=int
            ) or 0

            if qtd_devolver <= 0:
                continue

            saldos_tecnico = SaldoTecnico.query.filter(
                SaldoTecnico.tecnico_id == inventario.tecnico_id,
                SaldoTecnico.item_id == item_inv.item_id,
                SaldoTecnico.quantidade > 0
            )

            if inventario.tipo_servico_id:
                saldos_tecnico = saldos_tecnico.filter(
                    SaldoTecnico.tipo_servico_id == inventario.tipo_servico_id
                )

            saldos_tecnico = saldos_tecnico.order_by(SaldoTecnico.id.asc()).all()

            saldo_total = sum(int(s.quantidade or 0) for s in saldos_tecnico)

            if qtd_devolver > saldo_total:
                flash(
                    f'Quantidade maior que o saldo disponível para o item {item_inv.item.codigo}.',
                    'danger'
                )
                return redirect(url_for('inventario_tecnico.devolver_estoque', id=id))

            restante = qtd_devolver

            for saldo in saldos_tecnico:
                atual = int(saldo.quantidade or 0)

                if atual <= 0:
                    continue

                if atual >= restante:
                    saldo.quantidade = atual - restante
                    restante = 0
                    break

                saldo.quantidade = 0
                restante -= atual

            estoque = Estoque.query.filter_by(
                item_id=item_inv.item_id,
                tipo_servico_id=inventario.tipo_servico_id,
                tipo_estoque='empresa',
                cliente_id=None
            ).first()

            if not estoque:
                estoque = Estoque(
                    item_id=item_inv.item_id,
                    tipo_servico_id=inventario.tipo_servico_id,
                    tipo_estoque='empresa',
                    cliente_id=None,
                    quantidade=0,
                    quantidade_minima=0,
                    responsavel=inventario.responsavel or 'Inventário Técnico',
                    endereco=None
                )
                db.session.add(estoque)

            estoque.quantidade = int(estoque.quantidade or 0) + qtd_devolver
            houve_devolucao = True

        if not houve_devolucao:
            flash('Informe pelo menos uma quantidade para devolver ao estoque.', 'warning')
            return redirect(url_for('inventario_tecnico.devolver_estoque', id=id))

        db.session.commit()

        flash('Materiais devolvidos ao estoque com sucesso.', 'success')
        return redirect(url_for('inventario_tecnico.detalhes_inventario', id=id))

    return render_template(
        'inventario_tecnico/devolver_estoque.html',
        inventario=inventario
    )
