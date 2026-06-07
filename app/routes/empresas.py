from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required

from app.extensions import db
from app.models import Empresa, OrdemServico, TipoServico


empresas_bp = Blueprint(
    'empresas',
    __name__,
    url_prefix='/empresas'
)


# =========================
# LISTAR TODAS
# =========================
@empresas_bp.route('/')
@login_required
def lista_empresas():

    termo = request.args.get('busca', '').strip()

    query = Empresa.query

    if termo:
        query = query.filter(
            (Empresa.razao_social.ilike(f"%{termo}%")) |
            (Empresa.cnpj.ilike(f"%{termo}%"))
        )

    empresas = query.order_by(Empresa.razao_social.asc()).all()

    return render_template(
        'empresas/lista_empresas.html',
        empresas=empresas,
        titulo='Empresas / Parceiros',
        tipo_lista='todos'
    )


# =========================
# LISTAR CLIENTES
# =========================
@empresas_bp.route('/clientes')
@login_required
def lista_clientes():

    termo = request.args.get('busca', '').strip()

    query = Empresa.query.filter_by(tipo_empresa='cliente')

    if termo:
        query = query.filter(
            (Empresa.razao_social.ilike(f"%{termo}%")) |
            (Empresa.cnpj.ilike(f"%{termo}%"))
        )

    empresas = query.order_by(Empresa.razao_social.asc()).all()

    return render_template(
        'empresas/lista_empresas.html',
        empresas=empresas,
        titulo='Clientes Cadastrados',
        tipo_lista='cliente'
    )


# =========================
# LISTAR FORNECEDORES
# =========================
@empresas_bp.route('/fornecedores')
@login_required
def lista_fornecedores():

    termo = request.args.get('busca', '').strip()

    query = Empresa.query.filter_by(tipo_empresa='fornecedor')

    if termo:
        query = query.filter(
            (Empresa.razao_social.ilike(f"%{termo}%")) |
            (Empresa.cnpj.ilike(f"%{termo}%"))
        )

    empresas = query.order_by(Empresa.razao_social.asc()).all()

    return render_template(
        'empresas/lista_empresas.html',
        empresas=empresas,
        titulo='Fornecedores Cadastrados',
        tipo_lista='fornecedor'
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