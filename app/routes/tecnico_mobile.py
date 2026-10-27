from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import Usuario, Tecnico


bp_tecnico_mobile = Blueprint(
    "tecnico_mobile",
    __name__,
    url_prefix="/tecnico-mobile"
)


def get_tecnico_logado():
    if session.get("perfil_mobile") == "tecnico":
        tecnico_id = session.get("tecnico_id")
        if tecnico_id:
            tecnico = Tecnico.query.get(tecnico_id)
            if tecnico:
                return tecnico

    return None


def localizar_usuario_tecnico(login):
    login = (login or "").strip()
    login_normalizado = login.lower()

    usuario = (
        Usuario.query
        .filter(
            Usuario.perfil == "tecnico",
            or_(
                func.lower(Usuario.email) == login_normalizado,
                func.lower(Usuario.nome) == login_normalizado,
            )
        )
        .first()
    )

    tecnico = None

    if usuario:
        tecnico = getattr(usuario, "tecnico", None)
        if not tecnico and usuario.email:
            tecnico = (
                Tecnico.query
                .filter(func.lower(Tecnico.email) == usuario.email.lower())
                .first()
            )

    if not tecnico:
        tecnico = (
            Tecnico.query
            .filter(
                or_(
                    Tecnico.matricula == login,
                    func.lower(Tecnico.email) == login_normalizado,
                    func.lower(Tecnico.nome) == login_normalizado,
                )
            )
            .first()
        )

    if tecnico and not usuario:
        usuario = (
            Usuario.query
            .filter(
                Usuario.perfil == "tecnico",
                or_(
                    Usuario.tecnico_id == tecnico.id,
                    func.lower(Usuario.email) == (tecnico.email or "").lower(),
                    func.lower(Usuario.nome) == tecnico.nome.lower(),
                )
            )
            .first()
        )

    return usuario, tecnico


@bp_tecnico_mobile.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        login = (
            request.form.get("login")
            or request.form.get("email")
            or ""
        ).strip()

        senha = request.form.get("senha", "").strip()

        usuario, tecnico = localizar_usuario_tecnico(login)

        if not usuario or not check_password_hash(usuario.senha_hash, senha):
            flash("Login ou senha inválidos.", "danger")
            return redirect(url_for("tecnico_mobile.login"))

        # O navegador compartilha o cookie de sessão entre todas as abas.
        # Quando um administrador abre o portal técnico em outra aba, preserve
        # o login administrativo e mantenha apenas o contexto mobile separado.
        preservar_login_admin = (
            current_user.is_authenticated
            and getattr(current_user, "perfil", None) == "admin"
        )

        if not preservar_login_admin:
            logout_user()
            session.clear()
            login_user(usuario)

        if not tecnico:
            tecnico = getattr(usuario, "tecnico", None)

        if not tecnico and usuario.email:
            tecnico = Tecnico.query.filter_by(email=usuario.email).first()

        if not tecnico:
            flash("Usuário técnico não vinculado ao cadastro de técnico.", "danger")
            return redirect(url_for("tecnico_mobile.login"))

        if usuario.tecnico_id != tecnico.id:
            usuario.tecnico_id = tecnico.id
            db.session.commit()

        session["tecnico_id"] = tecnico.id
        session["tecnico_nome"] = tecnico.nome
        session["perfil_mobile"] = "tecnico"

        return redirect(url_for("tecnico_mobile.home"))

    return render_template("tecnico_mobile/login.html")


@bp_tecnico_mobile.route("/home")
@login_required
def home():

    tecnico = get_tecnico_logado()

    if not tecnico:
        flash("Faça login novamente.", "warning")
        return redirect(url_for("tecnico_mobile.login"))

    sucesso = request.args.get("sucesso")

    return render_template(
        "tecnico_mobile/home.html",
        tecnico=tecnico,
        sucesso=sucesso
    )


@bp_tecnico_mobile.route("/alterar-senha", methods=["GET", "POST"])
@login_required
def alterar_senha():

    tecnico = get_tecnico_logado()

    if not tecnico:
        flash("Técnico não localizado. Faça login novamente.", "warning")
        return redirect(url_for("tecnico_mobile.login"))

    if request.method == "POST":
        senha_atual = request.form.get("senha_atual", "").strip()
        nova_senha = request.form.get("nova_senha", "").strip()
        confirmar_senha = request.form.get("confirmar_senha", "").strip()

        if not senha_atual or not nova_senha or not confirmar_senha:
            flash("Preencha todos os campos.", "warning")
            return redirect(url_for("tecnico_mobile.alterar_senha"))

        usuario_tecnico = Usuario.query.filter_by(tecnico_id=tecnico.id).first()

        if not usuario_tecnico:
            flash("Usuário técnico não localizado.", "danger")
            return redirect(url_for("tecnico_mobile.alterar_senha"))

        if not check_password_hash(usuario_tecnico.senha_hash, senha_atual):
            flash("Senha atual incorreta.", "danger")
            return redirect(url_for("tecnico_mobile.alterar_senha"))

        if nova_senha != confirmar_senha:
            flash("A nova senha e a confirmação não conferem.", "warning")
            return redirect(url_for("tecnico_mobile.alterar_senha"))

        if len(nova_senha) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "warning")
            return redirect(url_for("tecnico_mobile.alterar_senha"))

        usuario_tecnico.senha_hash = generate_password_hash(nova_senha)
        db.session.commit()

        flash("Senha alterada com sucesso.", "success")
        return redirect(url_for("tecnico_mobile.home"))

    return render_template(
        "tecnico_mobile/alterar_senha.html",
        tecnico=tecnico
    )


@bp_tecnico_mobile.route("/logout")
@login_required
def logout():
    if getattr(current_user, "perfil", None) == "admin":
        session.pop("tecnico_id", None)
        session.pop("tecnico_nome", None)
        session.pop("perfil_mobile", None)
    else:
        logout_user()
        session.clear()
    return redirect(url_for("tecnico_mobile.login"))
