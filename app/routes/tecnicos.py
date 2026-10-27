from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Tecnico, Usuario
import qrcode
import os
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError
from app.drafts import draft_saved

bp = Blueprint('tecnicos', __name__, url_prefix='/tecnicos')


def limpar_cpf(cpf):
    return (
        cpf.replace(".", "")
           .replace("-", "")
           .replace(" ", "")
           .strip()
    )


def senha_inicial_tecnico(tecnico):
    return limpar_cpf(tecnico.cpf or "")[:6]


@bp.route('/cadastro', methods=['GET', 'POST'])
def cadastrar_tecnico():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        matricula = request.form.get('matricula', '').strip()
        cpf = request.form.get('cpf', '').strip()
        telefone = request.form.get('telefone', '').strip()
        email = request.form.get('email', '').strip()
        funcao = request.form.get('funcao', '').strip()
        status = request.form.get('status', 'Ativo').strip()

        if not nome or not matricula or not cpf:
            flash('Nome, Matrícula e CPF são obrigatórios.', 'danger')
            return redirect(url_for('tecnicos.cadastrar_tecnico'))

        tecnico_existente = Tecnico.query.filter_by(matricula=matricula).first()
        if tecnico_existente:
            flash('Matrícula já cadastrada.', 'danger')
            return redirect(url_for('tecnicos.cadastrar_tecnico'))

        cpf_existente = Tecnico.query.filter_by(cpf=cpf).first()
        if cpf_existente:
            flash('CPF já cadastrado.', 'danger')
            return redirect(url_for('tecnicos.cadastrar_tecnico'))

        novo_tecnico = Tecnico(
            nome=nome,
            matricula=matricula,
            cpf=cpf,
            telefone=telefone,
            email=email,
            funcao=funcao,
            status=status
        )

        db.session.add(novo_tecnico)
        db.session.commit()

        senha_gerada = senha_inicial_tecnico(novo_tecnico)
        senha_hash = generate_password_hash(senha_gerada)

        if email:
            usuario_existente = Usuario.query.filter_by(email=email).first()

            if not usuario_existente:
                novo_usuario = Usuario(
                    nome=nome,
                    email=email,
                    senha_hash=senha_hash,
                    perfil='tecnico',
                    tecnico=novo_tecnico
                )

                db.session.add(novo_usuario)
                db.session.commit()

                flash(
                    f'Técnico cadastrado com sucesso! Senha inicial: {senha_gerada}',
                    'success'
                )

            else:
                usuario_existente.tecnico = novo_tecnico
                usuario_existente.perfil = 'tecnico'

                db.session.commit()

                flash(
                    'Técnico cadastrado. O e-mail já existia e foi vinculado ao cadastro técnico.',
                    'warning'
                )
        else:
            flash(
                'Técnico cadastrado. Porém sem e-mail, o login técnico não poderá ser feito.',
                'warning'
            )

        login_tecnico_url = url_for(
            'tecnico_mobile.login',
            _external=True
        )
        draft_saved()

        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(login_tecnico_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        pasta_qrcodes = os.path.join('app', 'static', 'qrcodes')
        os.makedirs(pasta_qrcodes, exist_ok=True)

        filename = f'{novo_tecnico.nome.replace(" ", "_")}_{novo_tecnico.id}.png'
        filepath = os.path.join(pasta_qrcodes, filename)
        img.save(filepath)

        mensagem_whatsapp = f"""
Olá {nome}, segue seu link para acessar o Portal Técnico Mobile da World Telecom:

{login_tecnico_url}

Login: {email if email else '[sem email]'}
Senha inicial: {senha_gerada}

Ao acessar, você poderá:
- Solicitar materiais
- Registrar baixa técnica
- Consultar suas movimentações

Qualquer dúvida, entre em contato com o setor responsável.
"""

        return render_template(
            'tecnicos/link_gerado.html',
            nome=nome,
            tecnico_id=novo_tecnico.id,
            link=login_tecnico_url,
            qr_filename=filename,
            senha_gerada=senha_gerada,
            telefone=telefone,
            mensagem_whatsapp=mensagem_whatsapp
        )

    return render_template('tecnicos/cadastro.html')


@bp.route('/editar/<int:tecnico_id>', methods=['GET', 'POST'])
@login_required
def editar_tecnico(tecnico_id):
    if current_user.perfil not in ('admin', 'estoque'):
        abort(403)
    tecnico = Tecnico.query.get_or_404(tecnico_id)
    campos = ('nome', 'matricula', 'cpf', 'telefone', 'email', 'funcao', 'status')
    dados = {campo: getattr(tecnico, campo) or '' for campo in campos}
    if request.method == 'POST':
        dados = {campo: request.form.get(campo, '').strip() for campo in campos}
        erro = None
        cpf = limpar_cpf(dados['cpf'])
        usuarios = Usuario.query.filter_by(tecnico_id=tecnico.id).all()
        if not all(dados[campo] for campo in ('nome', 'matricula', 'cpf')):
            erro = 'Nome, matrícula e CPF são obrigatórios.'
        elif len(cpf) != 11 or not cpf.isdigit():
            erro = 'Informe um CPF com 11 números.'
        elif dados['status'] not in ('Ativo', 'Inativo'):
            erro = 'Selecione um status válido.'
        elif any(len(dados[campo]) > limite for campo, limite in
                 (('nome', 100), ('matricula', 20), ('telefone', 20), ('email', 100), ('funcao', 100))):
            erro = 'Um dos campos excedeu o tamanho permitido.'
        elif Tecnico.query.filter(Tecnico.id != tecnico.id, Tecnico.matricula == dados['matricula']).first():
            erro = 'Matrícula já cadastrada para outro técnico.'
        elif any(limpar_cpf(outro.cpf or '') == cpf for outro in
                 Tecnico.query.filter(Tecnico.id != tecnico.id).all()):
            erro = 'CPF já cadastrado para outro técnico.'
        elif usuarios and not dados['email']:
            erro = 'O técnico possui acesso vinculado e precisa manter um e-mail.'
        elif len(usuarios) > 1 and dados['email'] != (tecnico.email or ''):
            erro = 'O técnico possui mais de um acesso vinculado. Regularize os acessos antes de alterar o e-mail.'
        elif dados['email'] and ('@' not in dados['email'] or any(c.isspace() for c in dados['email'])):
            erro = 'Informe um e-mail válido.'
        elif dados['email'] and Tecnico.query.filter(Tecnico.id != tecnico.id, Tecnico.email == dados['email']).first():
            erro = 'E-mail já cadastrado para outro técnico.'
        elif dados['email'] and Usuario.query.filter(Usuario.email == dados['email']).filter(
                (Usuario.tecnico_id != tecnico.id) | Usuario.tecnico_id.is_(None)).first():
            erro = 'Este e-mail pertence a outro usuário. Informe um e-mail diferente.'
        if erro:
            flash(erro, 'danger')
            return render_template('tecnicos/editar.html', tecnico=tecnico, dados=dados), 400
        dados['cpf'] = f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'
        try:
            for campo, valor in dados.items():
                setattr(tecnico, campo, valor)
            # Keep the same technician ID, balances, history, password, and roles.
            for usuario in usuarios:
                usuario.nome = tecnico.nome
                if len(usuarios) == 1:
                    usuario.email = tecnico.email
                usuario.status = tecnico.status
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Não foi possível salvar: matrícula, CPF ou e-mail já utilizado.', 'danger')
            return render_template('tecnicos/editar.html', tecnico=tecnico, dados=dados), 400
        flash('Dados do técnico atualizados com sucesso.', 'success')
        return redirect(url_for('tecnicos.listar_tecnicos'))
    return render_template('tecnicos/editar.html', tecnico=tecnico, dados=dados)


@bp.route('/listagem', endpoint='listar_tecnicos')
def listar_tecnicos():
    filtro_status = request.args.get('status', '')

    query = Tecnico.query

    if filtro_status:
        query = query.filter_by(status=filtro_status)

    tecnicos = query.order_by(Tecnico.nome).all()

    return render_template(
        'tecnicos/listagem.html',
        tecnicos=tecnicos,
        filtro_status=filtro_status
    )


@bp.route('/qrcode/<int:tecnico_id>')
def qrcode_tecnico(tecnico_id):
    tecnico = Tecnico.query.get_or_404(tecnico_id)

    login_tecnico_url = url_for(
        'tecnico_mobile.login',
        _external=True
    )

    pasta_qrcodes = os.path.join('app', 'static', 'qrcodes')
    os.makedirs(pasta_qrcodes, exist_ok=True)

    nome_arquivo = f'{tecnico.nome.replace(" ", "_")}_{tecnico.id}.png'
    filepath = os.path.join(pasta_qrcodes, nome_arquivo)

    if not os.path.exists(filepath):
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(login_tecnico_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filepath)

    mensagem_whatsapp = f"""
Olá {tecnico.nome}, segue seu link para acessar o Portal Técnico Mobile da World Telecom:

{login_tecnico_url}

Login: {tecnico.email if tecnico.email else '[sem email]'}
Senha inicial: 6 primeiros números do CPF

Ao acessar, você poderá:
- Solicitar materiais
- Registrar baixa técnica

Qualquer dúvida, entre em contato com o setor responsável.
"""

    return render_template(
        'tecnicos/link_gerado.html',
        nome=tecnico.nome,
        tecnico_id=tecnico.id,
        link=login_tecnico_url,
        qr_filename=nome_arquivo,
        senha_gerada='6 primeiros números do CPF',
        telefone=tecnico.telefone,
        mensagem_whatsapp=mensagem_whatsapp
    )
    
@bp.route('/acesso/<int:tecnico_id>')
def acesso_tecnico(tecnico_id):
    tecnico = Tecnico.query.get_or_404(tecnico_id)

    senha_gerada = senha_inicial_tecnico(tecnico)

    link_login = url_for(
        'tecnico_mobile.login',
        _external=True
    )

    login_tecnico = tecnico.email if tecnico.email else tecnico.matricula

    mensagem_whatsapp = f"""Olá {tecnico.nome}, segue seu acesso ao Portal Técnico Mobile:

Link: {link_login}
Login: {login_tecnico}
Senha inicial: {senha_gerada}

Após acessar, você verá:
- Requisição de Materiais
- Baixa de Materiais
- Alterar Senha
"""

    return render_template(
        'tecnicos/acesso_tecnico.html',
        tecnico=tecnico,
        link_login=link_login,
        login_tecnico=login_tecnico,
        senha_gerada=senha_gerada,
        mensagem_whatsapp=mensagem_whatsapp
    )


@bp.route('/resetar-senha/<int:tecnico_id>', methods=['POST'])
@login_required
def resetar_senha_tecnico(tecnico_id):
    if current_user.perfil != 'admin':
        flash('Apenas administrador pode redefinir senha de técnico.', 'danger')
        return redirect(url_for('tecnicos.listar_tecnicos'))

    tecnico = Tecnico.query.get_or_404(tecnico_id)
    senha_gerada = senha_inicial_tecnico(tecnico)

    if len(senha_gerada) < 6:
        flash('CPF do técnico inválido para gerar senha inicial.', 'danger')
        return redirect(url_for('tecnicos.listar_tecnicos'))

    usuario = None

    if tecnico.email:
        usuario = Usuario.query.filter_by(email=tecnico.email).first()

    if not usuario:
        usuario = Usuario.query.filter_by(tecnico_id=tecnico.id).first()

    if not usuario:
        if not tecnico.email:
            flash('Técnico sem e-mail. Cadastre um e-mail antes de criar acesso.', 'danger')
            return redirect(url_for('tecnicos.listar_tecnicos'))

        usuario = Usuario(
            nome=tecnico.nome,
            email=tecnico.email,
            perfil='tecnico',
            tecnico=tecnico,
            senha_hash=generate_password_hash(senha_gerada)
        )
        db.session.add(usuario)
    else:
        usuario.nome = tecnico.nome
        usuario.perfil = 'tecnico'
        usuario.tecnico = tecnico
        usuario.senha_hash = generate_password_hash(senha_gerada)

    usuario.status = 'Ativo'
    db.session.commit()

    flash(
        f'Senha de {tecnico.nome} redefinida para os 6 primeiros números do CPF.',
        'success'
    )
    return redirect(url_for('tecnicos.listar_tecnicos'))


@bp.route('/alterar-status/<int:tecnico_id>', methods=['POST'])
def alterar_status(tecnico_id):
    tecnico = Tecnico.query.get_or_404(tecnico_id)

    novo_status = request.form.get('status', 'Ativo')
    tecnico.status = novo_status

    db.session.commit()

    flash(f'Status de {tecnico.nome} alterado para {novo_status}.', 'success')

    return redirect(url_for('tecnicos.listar_tecnicos'))
