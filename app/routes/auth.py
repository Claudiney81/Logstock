from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    session
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)
from flask_mail import Message
import os
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db, login_manager, mail
from app.models import Usuario


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@login_manager.user_loader
def load_user(user_id):
    try:
        return Usuario.query.get(int(user_id))
    except Exception:
        return None


# --------------------------------------------------
# TOKENS SEGUROS
# --------------------------------------------------
def gerar_token_login(usuario_id):
    s = URLSafeTimedSerializer(current_app.secret_key)
    return s.dumps(usuario_id, salt='login-direto')


def gerar_token_senha(usuario_id):
    s = URLSafeTimedSerializer(current_app.secret_key)
    return s.dumps(usuario_id, salt='redefinir-senha')


def carregar_usuario_por_token_login(token, max_age=3600):
    s = URLSafeTimedSerializer(current_app.secret_key)

    usuario_id = s.loads(
        token,
        salt='login-direto',
        max_age=max_age
    )

    return Usuario.query.get(usuario_id)


def carregar_usuario_por_token_senha(token, max_age=3600):
    s = URLSafeTimedSerializer(current_app.secret_key)

    usuario_id = s.loads(
        token,
        salt='redefinir-senha',
        max_age=max_age
    )

    return Usuario.query.get(usuario_id)


# --------------------------------------------------
# LOGIN DIRETO
# --------------------------------------------------
@auth_bp.route('/login-direto/<token>')
def login_direto(token):

    try:
        user = carregar_usuario_por_token_login(token, max_age=86400)

    except SignatureExpired:
        flash('Link expirado. Solicite um novo.', 'warning')
        return redirect(url_for('auth.login'))

    except BadSignature:
        flash('Token inválido.', 'danger')
        return redirect(url_for('auth.login'))

    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('auth.login'))

    login_user(user)
    flash(f'Login direto como {user.nome}', 'success')

    if user.perfil == 'tecnico':
        return redirect(url_for('baixa_tecnico.formulario_baixa', modo='mobile'))

    if user.perfil == 'tecnica':
        return redirect(url_for('requisicoes_tecnicos.recebidas'))

    if user.perfil == 'estoque':
        return redirect(url_for('estoque.estoque'))

    return redirect(url_for('home.home'))


# --------------------------------------------------
# LOGIN PADRÃO
# --------------------------------------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():

    if current_user.is_authenticated:
        if getattr(current_user, "perfil", None) == "tecnico":
            logout_user()
            session.clear()
            flash(
                "Acesso técnico encerrado. Entre com o perfil administrativo.",
                "info"
            )
        else:
            return redirect(url_for('home.home'))

    if request.method == 'POST':

        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()

        user = Usuario.query.filter_by(email=email).first()

        if user and check_password_hash(user.senha_hash, senha):
            login_user(user)
            flash('Login efetuado com sucesso!', 'success')

            if user.perfil == 'tecnico':
                return redirect(url_for('baixa_tecnico.formulario_baixa', modo='mobile'))

            if user.perfil == 'tecnica':
                return redirect(url_for('requisicoes_tecnicos.recebidas'))

            if user.perfil == 'estoque':
                return redirect(url_for('estoque.estoque'))

            return redirect(url_for('home.home'))

        flash('Email ou senha inválidos.', 'danger')

    return render_template('auth/login.html')


# --------------------------------------------------
# LOGIN TÉCNICO MOBILE
# --------------------------------------------------
@auth_bp.route('/login_tecnico', methods=['GET', 'POST'])
def login_tecnico():

    if current_user.is_authenticated and current_user.perfil == 'tecnico':
        return redirect(url_for('baixa_tecnico.formulario_baixa', modo='mobile'))

    if request.method == 'POST':

        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()

        user = Usuario.query.filter_by(
            email=email,
            perfil='tecnico'
        ).first()

        if user and check_password_hash(user.senha_hash, senha):
            login_user(user)

            session["tecnico_id"] = user.id
            session["tecnico_nome"] = user.nome
            session["perfil"] = "tecnico"

            return redirect(url_for('baixa_tecnico.formulario_baixa', modo='mobile'))

        flash('Credenciais inválidas ou usuário não é técnico.', 'danger')

    return render_template('baixa_tecnico/login_tecnico.html')


# --------------------------------------------------
# LOGOUT GERAL
# --------------------------------------------------
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))


# --------------------------------------------------
# LOGOUT TÉCNICO
# --------------------------------------------------
@auth_bp.route('/logout_tecnico')
def logout_tecnico():
    logout_user()
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('auth.login_tecnico'))


# --------------------------------------------------
# CADASTRO DE USUÁRIO - SOMENTE ADMIN
# --------------------------------------------------
@auth_bp.route('/registro', methods=['GET', 'POST'])
@login_required
def registro():

    if current_user.perfil != 'admin':
        flash('Acesso permitido apenas para administrador.', 'danger')
        return redirect(url_for('home.home'))

    if request.method == 'POST':

        nome = request.form.get('nome', '').strip()

        email = request.form.get(
            'cadastro_usuario_email',
            ''
        ).strip()

        senha = request.form.get(
            'cadastro_usuario_senha',
            ''
        ).strip()

        perfil = request.form.get('perfil', '').strip()
        mapa_perfis = {
            'Administrador': 'admin',
            'Estoque': 'estoque',
            'Área Técnica': 'tecnica',
            'Técnico': 'tecnico',
            'admin': 'admin',
            'estoque': 'estoque',
            'tecnica': 'tecnica',
            'tecnico': 'tecnico'
        }

        perfil = mapa_perfis.get(perfil)

        if not nome or not email or not senha or not perfil:
            flash('Preencha todos os campos corretamente.', 'warning')
            return redirect(url_for('auth.registro'))

        if Usuario.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'warning')
            return redirect(url_for('auth.registro'))

        novo_usuario = Usuario(
            nome=nome,
            email=email,
            senha_hash=generate_password_hash(senha),
            perfil=perfil
        )

        db.session.add(novo_usuario)
        db.session.commit()

        flash('Usuário registrado com sucesso!', 'success')
        return redirect(url_for('auth.registro'))

    return render_template('auth/registro.html')


# --------------------------------------------------
# ESQUECI MINHA SENHA
# --------------------------------------------------
@auth_bp.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():

    if request.method == 'POST':

        email = request.form.get('email', '').strip()

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario:

            token = gerar_token_senha(usuario.id)

            link = url_for(
                'auth.redefinir_senha',
                token=token,
                _external=True
            )

            msg = Message(
                subject='Redefinição de senha - LogiStock',
                recipients=[usuario.email],
                body=f'''
Olá, {usuario.nome}.

Recebemos uma solicitação para redefinir sua senha no LogiStock.

Clique no link abaixo para criar uma nova senha:

{link}

Este link expira em 1 hora.

Se você não solicitou esta alteração, ignore este e-mail.

LogiStock
'''
            )

            try:

                brevo_api_key = os.getenv("BREVO_API_KEY")

                if not brevo_api_key:
                    raise RuntimeError("BREVO_API_KEY não configurada")

                payload = {
                    "sender": {
                        "name": os.getenv(
                            "BREVO_SENDER_NAME",
                            "LogiStock"
                        ),
                        "email": os.getenv(
                                "BREVO_SENDER_EMAIL",
                                current_app.config["MAIL_DEFAULT_SENDER"][1]
                        )
                                            },
                    "to": [
                        {
                            "email": usuario.email,
                            "name": usuario.nome
                        }
                    ],
                    "subject": "Redefinição de senha - LogiStock",
                    "textContent": msg.body
                }

                response = requests.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={
                        "accept": "application/json",
                        "api-key": brevo_api_key,
                        "content-type": "application/json"
                    },
                    json=payload,
                    timeout=15
                )

                response.raise_for_status()

                current_app.logger.info(
                    "E-mail de redefinição enviado para usuário id=%s",
                    usuario.id
                )

            except Exception:
                current_app.logger.exception(
                    "Erro ao enviar e-mail de redefinição para usuário id=%s",
                    usuario.id
                )

        flash(
            'Se o e-mail estiver cadastrado, você receberá um link para redefinir sua senha.',
            'info'
        )

        return redirect(url_for('auth.login'))

    return render_template('auth/esqueci_senha.html')

# --------------------------------------------------
# REDEFINIR SENHA
# --------------------------------------------------
@auth_bp.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):

    try:
        usuario = carregar_usuario_por_token_senha(token, max_age=3600)

    except SignatureExpired:
        flash('Link expirado. Solicite uma nova redefinição de senha.', 'warning')
        return redirect(url_for('auth.esqueci_senha'))

    except BadSignature:
        flash('Link inválido.', 'danger')
        return redirect(url_for('auth.login'))

    if not usuario:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':

        senha = request.form.get('senha', '').strip()
        confirmar_senha = request.form.get('confirmar_senha', '').strip()

        if not senha or not confirmar_senha:
            flash('Preencha todos os campos.', 'warning')
            return redirect(request.url)

        if senha != confirmar_senha:
            flash('As senhas não conferem.', 'warning')
            return redirect(request.url)

        usuario.senha_hash = generate_password_hash(senha)

        db.session.commit()

        flash('Senha redefinida com sucesso. Faça login novamente.', 'success')
        return redirect(url_for('auth.login'))

    return render_template(
        'auth/redefinir_senha.html',
        token=token
    )
