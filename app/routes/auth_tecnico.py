from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Usuario, db
from werkzeug.security import check_password_hash
from urllib.parse import unquote

auth_tecnico = Blueprint('auth_tecnico', __name__)

@auth_tecnico.route('/login-tecnico', methods=['GET', 'POST'])
def login_tecnico():
    if request.method == 'POST':
        login = request.form['login']
        senha = request.form['senha']

        usuario = Usuario.query.filter_by(login=login, perfil='tecnico').first()
        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.id
            session['perfil'] = 'tecnico'
            session['nome_usuario'] = usuario.nome

            if usuario.tecnico:
                session['tecnico_id'] = usuario.tecnico.id
                session['tecnico_nome'] = usuario.tecnico.nome

            # ⚠️ Trata o redirecionamento com base no parâmetro ?next=
            next_page = request.args.get('next')
            if next_page:
                return redirect(unquote(next_page))
            return redirect(url_for('baixa_tecnico.formulario_baixa'))

        flash('Login ou senha inválidos.', 'danger')

    return render_template('baixas_mobile/login_tecnico.html')
