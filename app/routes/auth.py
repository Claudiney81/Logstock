from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.extensions import db, login_manager
from app.models import Usuario

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# -----------------------------
# Função para gerar token seguro
# -----------------------------
def gerar_token_login(usuario_id):
    s = URLSafeTimedSerializer(current_app.secret_key)
    return s.dumps(usuario_id, salt='login-direto')

# -----------------------------
# Login Direto (sem senha)
# -----------------------------
@auth_bp.route('/login-direto/<token>')
def login_direto(token):
    s = URLSafeTimedSerializer(current_app.secret_key)
    try:
        usuario_id = s.loads(token, salt='login-direto', max_age=86400)  # expira em 24h
    except SignatureExpired:
        flash('Link expirado. Solicite um novo.', 'warning')
        return redirect(url_for('auth.login'))
    except BadSignature:
        flash('Token inválido.', 'danger')
        return redirect(url_for('auth.login'))

    user = Usuario.query.get(usuario_id)
    if user:
        login_user(user)
        flash(f'Login direto como {user.nome}', 'success')

        # Redirecionamento por perfil
        if user.perfil == 'tecnico':
            return redirect(url_for('baixa_tecnico.formulario_baixa', modo='mobile'))
        elif user.perfil == 'tecnica':
            return redirect(url_for('requisicoes_tecnicos.recebidas'))
        elif user.perfil == 'estoque':
            return redirect(url_for('estoque.estoque'))
        else:
            return redirect(url_for('home.home'))
    else:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('auth.login'))

# -----------------------------
# Login padrão com email/senha
# -----------------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home.home'))

    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        user = Usuario.query.filter_by(email=email).first()

        if user and check_password_hash(user.senha_hash, senha):
            login_user(user)
            flash('Login efetuado com sucesso!', 'success')

            # Redirecionamento por perfil
            if user.perfil == 'tecnico':
                return redirect(url_for('baixa_tecnico.formulario_baixa', modo='mobile'))
            elif user.perfil == 'tecnica':
                return redirect(url_for('requisicoes_tecnicos.recebidas'))
            elif user.perfil == 'estoque':
                return redirect(url_for('estoque.estoque'))
            else:
                return redirect(url_for('home.home'))
        else:
            flash('Email ou senha inválidos.', 'danger')

    return render_template('auth/login.html')

# -----------------------------
# Login específico para técnicos (mobile)
# -----------------------------
# Em auth.py

@auth_bp.route('/login_tecnico', methods=['GET', 'POST'])
def login_tecnico():
    if current_user.is_authenticated and current_user.perfil == 'tecnico':
        return redirect(url_for('baixa_tecnico.formulario_baixa', modo='mobile'))

    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        user = Usuario.query.filter_by(email=email, perfil='tecnico').first()

        if user and check_password_hash(user.senha_hash, senha):
            login_user(user)
            session["tecnico_id"] = user.id
            session["tecnico_nome"] = user.nome
            session["perfil"] = "tecnico"
            return redirect(url_for('baixa_tecnico.formulario_baixa', modo='mobile'))
        else:
            flash('Credenciais inválidas ou usuário não é técnico.', 'danger')

    return render_template('baixa_tecnico/login_tecnico.html')

# -----------------------------
# Logout geral
# -----------------------------
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))

# -----------------------------
# Logout específico para técnico
# -----------------------------
@auth_bp.route('/logout_tecnico')
def logout_tecnico():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('auth.login_tecnico'))

# -----------------------------
# Registro de novo usuário
# -----------------------------
@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for('home.home'))

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        perfil = request.form['perfil']

        # Normalização do valor do perfil
        if perfil == 'Administrador':
            perfil = 'admin'
        elif perfil == 'Estoque':
            perfil = 'estoque'
        elif perfil == 'Área Técnica':
            perfil = 'tecnica'

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
        flash('Usuário registrado com sucesso! Faça login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/registro.html')
