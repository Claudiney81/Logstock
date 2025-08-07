from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Tecnico, Usuario
import qrcode
import os
from werkzeug.security import generate_password_hash

bp = Blueprint('tecnicos', __name__, url_prefix='/tecnicos')


@bp.route('/cadastro', methods=['GET', 'POST'])
def cadastrar_tecnico():
    if request.method == 'POST':
        nome = request.form['nome']
        matricula = request.form['matricula']
        cpf = request.form['cpf']
        telefone = request.form['telefone']
        email = request.form['email']
        area_tecnica = request.form['area_tecnica']
        status = request.form['status']

        if not nome or not matricula or not cpf:
            flash('Nome, Matrícula e CPF são obrigatórios.', 'danger')
            return redirect(url_for('tecnicos.cadastrar_tecnico'))

        tecnico_existente = Tecnico.query.filter_by(matricula=matricula).first()
        if tecnico_existente:
            flash('Matrícula já cadastrada.', 'danger')
            return redirect(url_for('tecnicos.cadastrar_tecnico'))

        novo_tecnico = Tecnico(
            nome=nome,
            matricula=matricula,
            cpf=cpf,
            telefone=telefone,
            email=email,
            area_tecnica=area_tecnica,
            status=status
        )
        db.session.add(novo_tecnico)
        db.session.commit()

        # Gerar senha a partir do CPF (6 primeiros números)
        senha_gerada = cpf.replace(".", "").replace("-", "")  # usa CPF inteiro
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
                flash(f'Técnico cadastrado com sucesso! Senha de acesso: {senha_gerada}', 'success')
            else:
                flash('Técnico cadastrado, mas o e-mail já está vinculado a um usuário existente.', 'warning')
        else:
            flash(f'Técnico cadastrado. Porém sem e-mail, o login técnico não poderá ser feito.', 'warning')

        # Geração de link e QR code
        login_tecnico_url = url_for(
            'auth.login_tecnico',
            next=url_for('baixa_tecnico.formulario_baixa', modo='mobile'),
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
Olá {nome}, segue seu link para acessar o sistema de baixa técnica da World Telecom:

{login_tecnico_url}

Login: {email if email else '[sem email]'}
Senha: {senha_gerada}

Qualquer dúvida, entre em contato com o setor responsável.
"""

        return render_template(
            'tecnicos/link_gerado.html',
            nome=nome,
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
    return render_template('tecnicos/listagem.html', tecnicos=tecnicos, filtro_status=filtro_status)


@bp.route('/qrcode/<int:tecnico_id>')
def qrcode_tecnico(tecnico_id):
    tecnico = Tecnico.query.get_or_404(tecnico_id)

    login_tecnico_url = url_for(
        'auth.login_tecnico',
        next=url_for('baixa_tecnico.formulario_baixa', modo='mobile'),
        _external=True
    )

    nome_arquivo = f'{tecnico.nome.replace(" ", "_")}_{tecnico.id}.png'
    return render_template(
        'tecnicos/link_gerado.html',
        nome=tecnico.nome,
        link=login_tecnico_url,
        qr_filename=nome_arquivo,
        senha_gerada='******',
        telefone=tecnico.telefone,
        mensagem_whatsapp=""
    )


@bp.route('/alterar-status/<int:tecnico_id>', methods=['POST'])
def alterar_status(tecnico_id):
    tecnico = Tecnico.query.get_or_404(tecnico_id)
    novo_status = request.form.get('status')
    tecnico.status = novo_status
    db.session.commit()
    flash(f'Status de {tecnico.nome} alterado para {novo_status}.', 'success')
    return redirect(url_for('tecnicos.listar_tecnicos'))
