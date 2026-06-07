from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Tecnico, Usuario
import qrcode
import os
from werkzeug.security import generate_password_hash

bp = Blueprint('tecnicos', __name__, url_prefix='/tecnicos')


def limpar_cpf(cpf):
    return (
        cpf.replace(".", "")
           .replace("-", "")
           .replace(" ", "")
           .strip()
    )


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

        cpf_limpo = limpar_cpf(cpf)
        senha_gerada = cpf_limpo[:6]
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

    cpf_limpo = limpar_cpf(tecnico.cpf)
    senha_gerada = cpf_limpo[:6]

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


@bp.route('/alterar-status/<int:tecnico_id>', methods=['POST'])
def alterar_status(tecnico_id):
    tecnico = Tecnico.query.get_or_404(tecnico_id)

    novo_status = request.form.get('status', 'Ativo')
    tecnico.status = novo_status

    db.session.commit()

    flash(f'Status de {tecnico.nome} alterado para {novo_status}.', 'success')

    return redirect(url_for('tecnicos.listar_tecnicos'))