from datetime import datetime
from io import BytesIO

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Empresa, OrdemServico, TipoServico


empresas_bp = Blueprint(
    'empresas',
    __name__,
    url_prefix='/empresas'
)


def _empresas_query(tipo_lista, termo):
    query = Empresa.query

    if tipo_lista in ['cliente', 'fornecedor']:
        query = query.filter_by(tipo_empresa=tipo_lista)

    if termo:
        query = query.filter(
            (Empresa.razao_social.ilike(f"%{termo}%")) |
            (Empresa.cnpj.ilike(f"%{termo}%")) |
            (Empresa.email.ilike(f"%{termo}%")) |
            (Empresa.contato.ilike(f"%{termo}%"))
        )

    return query.order_by(Empresa.razao_social.asc())


def _contadores_empresas():
    total = db.session.query(func.count(Empresa.id)).scalar() or 0
    clientes = (
        db.session.query(func.count(Empresa.id))
        .filter(Empresa.tipo_empresa == 'cliente')
        .scalar()
        or 0
    )
    fornecedores = (
        db.session.query(func.count(Empresa.id))
        .filter(Empresa.tipo_empresa == 'fornecedor')
        .scalar()
        or 0
    )
    ordens_abertas = (
        db.session.query(func.count(OrdemServico.id))
        .filter(OrdemServico.status.in_(['aberta', 'em_andamento']))
        .scalar()
        or 0
    )

    return {
        'total': total,
        'clientes': clientes,
        'fornecedores': fornecedores,
        'ordens_abertas': ordens_abertas
    }


def _contadores_contexto(tipo_lista, empresas):
    if tipo_lista == 'cliente':
        ids_clientes = [empresa.id for empresa in empresas]

        ordens_total = 0
        ordens_abertas = 0

        if ids_clientes:
            ordens_total = (
                db.session.query(func.count(OrdemServico.id))
                .filter(OrdemServico.cliente_id.in_(ids_clientes))
                .scalar()
                or 0
            )

            ordens_abertas = (
                db.session.query(func.count(OrdemServico.id))
                .filter(OrdemServico.cliente_id.in_(ids_clientes))
                .filter(OrdemServico.status.in_(['aberta', 'em_andamento']))
                .scalar()
                or 0
            )

        return {
            'cadastros': len(empresas),
            'ordens_total': ordens_total,
            'ordens_abertas': ordens_abertas
        }

    if tipo_lista == 'fornecedor':
        com_email = sum(1 for empresa in empresas if empresa.email)
        com_contato = sum(1 for empresa in empresas if empresa.contato)

        return {
            'cadastros': len(empresas),
            'com_email': com_email,
            'com_contato': com_contato
        }

    return _contadores_empresas()


def _renderizar_lista_empresas(tipo_lista, titulo):
    termo = request.args.get('busca', '').strip()
    empresas = _empresas_query(tipo_lista, termo).all()

    return render_template(
        'empresas/lista_empresas.html',
        empresas=empresas,
        titulo=titulo,
        tipo_lista=tipo_lista,
        contadores=_contadores_contexto(tipo_lista, empresas)
    )


# =========================
# LISTAR TODAS
# =========================
@empresas_bp.route('/')
@login_required
def lista_empresas():
    return _renderizar_lista_empresas(
        'todos',
        'Empresas / Parceiros'
    )


# =========================
# LISTAR CLIENTES
# =========================
@empresas_bp.route('/clientes')
@login_required
def lista_clientes():
    return _renderizar_lista_empresas(
        'cliente',
        'Clientes Cadastrados'
    )


# =========================
# LISTAR FORNECEDORES
# =========================
@empresas_bp.route('/fornecedores')
@login_required
def lista_fornecedores():
    return _renderizar_lista_empresas(
        'fornecedor',
        'Fornecedores Cadastrados'
    )


@empresas_bp.route('/exportar_excel')
@login_required
def exportar_empresas_excel():

    import pandas as pd

    tipo_lista = request.args.get('tipo_lista', 'todos')
    termo = request.args.get('busca', '').strip()

    if tipo_lista not in ['todos', 'cliente', 'fornecedor']:
        tipo_lista = 'todos'

    empresas = _empresas_query(tipo_lista, termo).all()

    linhas = []

    for empresa in empresas:
        ordens = getattr(empresa, 'ordens_servico', [])
        ordens_abertas = [
            os for os in ordens
            if (os.status or 'aberta') in ['aberta', 'em_andamento']
        ]

        linhas.append({
            'Razão Social': empresa.razao_social,
            'CNPJ': empresa.cnpj,
            'Tipo': (empresa.tipo_empresa or 'empresa').capitalize(),
            'Endereço': empresa.endereco or '-',
            'Contato': empresa.contato or '-',
            'Email': empresa.email or '-',
            'O.S Total': len(ordens),
            'O.S Abertas': len(ordens_abertas),
            'Observações': empresa.observacoes or '-'
        })

    output = BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df = pd.DataFrame(linhas)

        if df.empty:
            df = pd.DataFrame([{
                'Mensagem': 'Nenhum cadastro encontrado.'
            }])

        df.to_excel(
            writer,
            index=False,
            sheet_name='Empresas'
        )

        workbook = writer.book
        worksheet = writer.sheets['Empresas']

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#002B55',
            'font_color': '#FFFFFF',
            'border': 1
        })

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            largura = max(14, min(42, len(str(value)) + 8))
            worksheet.set_column(col_num, col_num, largura)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

    output.seek(0)

    data_arquivo = datetime.now().strftime('%Y%m%d_%H%M%S')

    return send_file(
        output,
        as_attachment=True,
        download_name=f'empresas_{tipo_lista}_{data_arquivo}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# =========================
# CADASTRAR EMPRESA - ROTA ANTIGA
# =========================
@empresas_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar_empresa():

    if request.method == 'POST':

        tipo_empresa = request.form.get('tipo_empresa') or 'cliente'

        nova_empresa = Empresa(
            razao_social=request.form['razao_social'],
            cnpj=request.form['cnpj'],
            endereco=request.form.get('endereco'),
            contato=request.form.get('contato'),
            email=request.form.get('email'),
            tipo_empresa=tipo_empresa,
            observacoes=request.form.get('observacoes')
        )

        try:
            db.session.add(nova_empresa)
            db.session.commit()

            flash(
                'Empresa cadastrada com sucesso!',
                'success'
            )

            return redirect(
                url_for('empresas.lista_empresas')
            )

        except Exception as e:
            db.session.rollback()

            print("ERRO AO CADASTRAR EMPRESA:", e)

            flash(
                'Erro ao cadastrar empresa.',
                'danger'
            )

    return render_template(
        'empresas/cadastro_empresa.html',
        tipo='empresa',
        titulo='Cadastro de Empresa / Parceiro'
    )


# =========================
# CADASTRAR CLIENTE
# =========================
@empresas_bp.route('/cadastrar_cliente', methods=['GET', 'POST'])
@login_required
def cadastrar_cliente():

    if request.method == 'POST':

        nova_empresa = Empresa(
            razao_social=request.form['razao_social'],
            cnpj=request.form['cnpj'],
            endereco=request.form.get('endereco'),
            contato=request.form.get('contato'),
            email=request.form.get('email'),
            tipo_empresa='cliente',
            observacoes=request.form.get('observacoes')
        )

        try:
            db.session.add(nova_empresa)
            db.session.commit()

            flash('Cliente cadastrado com sucesso!', 'success')
            return redirect(url_for('empresas.lista_clientes'))

        except Exception as e:
            db.session.rollback()
            print("ERRO AO CADASTRAR CLIENTE:", e)
            flash('Erro ao cadastrar cliente.', 'danger')

    return render_template(
        'empresas/cadastro_empresa.html',
        tipo='cliente',
        titulo='Cadastro de Cliente'
    )
    
@empresas_bp.route('/nova-os/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def nova_os(cliente_id):

    cliente = Empresa.query.get_or_404(cliente_id)
    tipos_servico = TipoServico.query.order_by(TipoServico.nome.asc()).all()

    if request.method == 'POST':

        ultima_os = (
            OrdemServico.query
            .order_by(OrdemServico.id.desc())
            .first()
        )

        proximo_numero = 1

        if ultima_os and ultima_os.numero_os:
            try:
                proximo_numero = int(
                    ultima_os.numero_os.replace('OS-', '')
                ) + 1
            except:
                pass

        numero_os = f'OS-{proximo_numero:04d}'

        nova = OrdemServico(
            numero_os=numero_os,
            cliente_id=cliente.id,
            tipo_servico_id=request.form.get('tipo_servico_id') or None,
            endereco=request.form.get('endereco') or cliente.endereco,
            responsavel=request.form.get('responsavel'),
            observacao=request.form.get('observacao'),
            status='aberta'
        )

        try:
            db.session.add(nova)
            db.session.commit()

            flash(f'O.S {numero_os} aberta com sucesso para {cliente.razao_social}.', 'success')
            return redirect(url_for('empresas.lista_clientes'))

        except Exception as e:
            db.session.rollback()
            print("ERRO AO ABRIR OS:", e)
            flash('Erro ao abrir O.S.', 'danger')

    return render_template(
        'empresas/nova_os.html',
        cliente=cliente,
        tipos_servico=tipos_servico
    )
    
    # =========================
# LISTAR O.S DO CLIENTE
# =========================
@empresas_bp.route('/ordens-servico/<int:cliente_id>')
@login_required
def listar_os_cliente(cliente_id):

    cliente = Empresa.query.get_or_404(cliente_id)

    ordens = (
        OrdemServico.query
        .filter_by(cliente_id=cliente.id)
        .order_by(OrdemServico.id.desc())
        .all()
    )

    return render_template(
        'empresas/listar_os_cliente.html',
        cliente=cliente,
        ordens=ordens
    )


@empresas_bp.route('/ordens-servico/<int:cliente_id>/excel')
@login_required
def exportar_os_cliente_excel(cliente_id):

    import pandas as pd

    cliente = Empresa.query.get_or_404(cliente_id)

    ordens = (
        OrdemServico.query
        .filter_by(cliente_id=cliente.id)
        .order_by(OrdemServico.id.desc())
        .all()
    )

    linhas = []

    for os in ordens:
        linhas.append({
            'O.S': os.numero_os,
            'Cliente': cliente.razao_social,
            'CNPJ': cliente.cnpj or '-',
            'Tipo Serviço': os.tipo_servico.nome if os.tipo_servico else '-',
            'Endereço': os.endereco or '-',
            'Responsável': os.responsavel or '-',
            'Status': os.status or 'aberta',
            'Data Abertura': (
                os.data_abertura.strftime('%d/%m/%Y %H:%M')
                if os.data_abertura else '-'
            ),
            'Observação': os.observacao or '-'
        })

    output = BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df = pd.DataFrame(linhas)

        if df.empty:
            df = pd.DataFrame([{
                'Mensagem': 'Nenhuma Ordem de Serviço encontrada.'
            }])

        df.to_excel(
            writer,
            index=False,
            sheet_name='Ordens de Serviço'
        )

        workbook = writer.book
        worksheet = writer.sheets['Ordens de Serviço']

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#002B55',
            'font_color': '#FFFFFF',
            'border': 1
        })

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            largura = max(14, min(42, len(str(value)) + 8))
            worksheet.set_column(col_num, col_num, largura)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

    output.seek(0)

    data_arquivo = datetime.now().strftime('%Y%m%d_%H%M%S')

    return send_file(
        output,
        as_attachment=True,
        download_name=f'ordens_servico_cliente_{cliente.id}_{data_arquivo}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
# =========================
# CADASTRAR FORNECEDOR
# =========================
@empresas_bp.route('/cadastrar_fornecedor', methods=['GET', 'POST'])
@login_required
def cadastrar_fornecedor():

    if request.method == 'POST':

        nova_empresa = Empresa(
            razao_social=request.form['razao_social'],
            cnpj=request.form['cnpj'],
            endereco=request.form.get('endereco'),
            contato=request.form.get('contato'),
            email=request.form.get('email'),
            tipo_empresa='fornecedor',
            observacoes=request.form.get('observacoes')
        )

        try:
            db.session.add(nova_empresa)
            db.session.commit()

            flash(
                'Fornecedor cadastrado com sucesso!',
                'success'
            )

            return redirect(
                url_for('empresas.lista_fornecedores')
            )

        except Exception as e:
            db.session.rollback()

            print("ERRO AO CADASTRAR FORNECEDOR:", e)

            flash(
                'Erro ao cadastrar fornecedor.',
                'danger'
            )

    return render_template(
        'empresas/cadastro_empresa.html',
        tipo='fornecedor',
        titulo='Cadastro de Fornecedor'
    )


# =========================
# EDITAR
# =========================
@empresas_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_empresa(id):

    empresa = Empresa.query.get_or_404(id)

    if request.method == 'POST':

        empresa.razao_social = request.form['razao_social']
        empresa.cnpj = request.form['cnpj']
        empresa.endereco = request.form.get('endereco')
        empresa.contato = request.form.get('contato')
        empresa.email = request.form.get('email')

        tipo_form = request.form.get('tipo_empresa')
        if tipo_form:
            empresa.tipo_empresa = tipo_form

        empresa.observacoes = request.form.get('observacoes')

        try:
            db.session.commit()

            flash(
                'Cadastro editado com sucesso!',
                'success'
            )

            if empresa.tipo_empresa == 'cliente':
                return redirect(
                    url_for('empresas.lista_clientes')
                )

            if empresa.tipo_empresa == 'fornecedor':
                return redirect(
                    url_for('empresas.lista_fornecedores')
                )

            return redirect(
                url_for('empresas.lista_empresas')
            )

        except Exception as e:
            db.session.rollback()

            print("ERRO AO EDITAR EMPRESA:", e)

            flash(
                'Erro ao editar cadastro.',
                'danger'
            )

    return render_template(
        'empresas/cadastro_empresa.html',
        empresa=empresa,
        tipo=empresa.tipo_empresa,
        titulo='Editar Cliente' if empresa.tipo_empresa == 'cliente' else 'Editar Fornecedor'
    )


# =========================
# EXCLUIR
# =========================
@empresas_bp.route('/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_empresa(id):

    empresa = Empresa.query.get_or_404(id)
    tipo_empresa = empresa.tipo_empresa

    try:
        db.session.delete(empresa)
        db.session.commit()

        flash(
            'Cadastro excluído com sucesso!',
            'success'
        )

    except Exception as e:
        db.session.rollback()

        print("ERRO AO EXCLUIR:", e)

        flash(
            'Erro ao excluir cadastro.',
            'danger'
        )

    if tipo_empresa == 'cliente':
        return redirect(
            url_for('empresas.lista_clientes')
        )

    if tipo_empresa == 'fornecedor':
        return redirect(
            url_for('empresas.lista_fornecedores')
        )

    return redirect(
        url_for('empresas.lista_empresas')
    )
    
    # =========================
# API - O.S DO CLIENTE
# =========================
@empresas_bp.route('/ordens-servico-json/<int:cliente_id>')
@login_required
def ordens_servico_json(cliente_id):

    ordens = (
        OrdemServico.query
        .filter_by(cliente_id=cliente_id)
        .order_by(OrdemServico.id.desc())
        .all()
    )

    return jsonify([
        {
            'id': os.id,
            'numero_os': os.numero_os,
            'endereco': os.endereco or ''
        }
        for os in ordens
    ])
    
# ==================================================
# EDITAR ORDEM DE SERVIÇO
# ==================================================
@empresas_bp.route('/ordem-servico/editar/<int:os_id>', methods=['GET', 'POST'])
@login_required
def editar_os(os_id):

    os = OrdemServico.query.get_or_404(os_id)

    cliente = Empresa.query.get_or_404(
        os.cliente_id
    )

    tipos_servico = (
        TipoServico.query
        .order_by(TipoServico.nome)
        .all()
    )

    if request.method == 'POST':

        os.tipo_servico_id = (
            request.form.get('tipo_servico_id') or None
        )

        os.endereco = request.form.get(
            'endereco'
        )

        os.responsavel = request.form.get(
            'responsavel'
        )

        os.status = request.form.get(
            'status'
        ) or 'aberta'

        os.observacao = request.form.get(
            'observacao'
        )

        db.session.commit()

        flash(
            'O.S atualizada com sucesso.',
            'success'
        )

        return redirect(
            url_for(
                'empresas.listar_os_cliente',
                cliente_id=cliente.id
            )
        )

    return render_template(
        'empresas/editar_os.html',
        os=os,
        cliente=cliente,
        tipos_servico=tipos_servico
    )
