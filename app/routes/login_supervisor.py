# app/login_supervisor.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user
from app.models import Usuario
from werkzeug.security import check_password_hash

bp_login_supervisor = Blueprint('login_supervisor', __name__, url_prefix='/login-supervisor')

@bp_login_supervisor.route('/', methods=['GET', 'POST'])
def login_supervisor():
    if request.method == 'POST':
        login = request.form.get('login')
        senha = request.form.get('senha')
        remember = bool(request.form.get('remember'))

        user = Usuario.query.filter_by(email=login).first()

        # ✅ Permite supervisor (e também admin/estoque/tecnica)
        if user and user.perfil in ['admin', 'estoque', 'tecnica', 'supervisor'] and check_password_hash(user.senha_hash, senha):
            login_user(user, remember=remember)
            # ✅ Vai direto ao formulário mobile de requisição
            return redirect(url_for('requisicoes_tecnicos.nova_requisicao_mobile'))

        flash('Login inválido. Verifique suas credenciais.', 'danger')

    return render_template('login_supervisor.html')

@bp_login_supervisor.route('/logout')
def logout_supervisor():
    logout_user()
    session.clear()
    return redirect(url_for('login_supervisor.login_supervisor'))
