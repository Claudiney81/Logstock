"""Public, read-only browsing for the training environment."""
from flask import abort, g, has_request_context, redirect, request, url_for
from flask_login import current_user, login_user
from sqlalchemy import event

from app.extensions import db
from app.models import Usuario


def init_demo(app):
    if not app.config.get("LOGISTOCK_DEMO_PUBLICO", False):
        return

    @app.before_request
    def public_demo():
        if request.endpoint == "static" or request.path == "/health":
            return
        # A separate, transient identity never becomes a database administrator.
        if not current_user.is_authenticated:
            login_user(Usuario(id=-1, nome="Visitante demonstração",
                               email="demo@example.invalid", perfil="admin",
                               status="Ativo"), fresh=False)
        if current_user.get_id() != "-1":
            return
        g.public_demo = True
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            abort(403, description="Demonstração: alterações não são permitidas.")
        if request.path in ("/auth/login", "/auth/logout", "/logout"):
            return redirect(url_for("home.home"))
        if (request.path.startswith(("/auth/", "/backup", "/_bootstrap_admin",
                                     "/tecnicos/acesso/", "/tecnicos/qrcode/"))
                or any(word in request.path.lower() for word in
                       ("excluir", "deletar", "remover", "limpar", "resetar"))):
            abort(403, description="Recurso indisponível na demonstração pública.")

    # Some legacy GET handlers can write too. Guard the database connection,
    # covering ORM flushes and direct SQL before any statement is executed.
    with app.app_context():
        @event.listens_for(db.engine, "before_cursor_execute")
        def prevent_demo_writes(connection, cursor, statement, parameters,
                                context, executemany):
            if has_request_context() and g.get("public_demo"):
                if statement.lstrip().split(None, 1)[0].upper() not in ("SELECT", "EXPLAIN"):
                    abort(403, description="Demonstração: alterações não são permitidas.")

    @app.context_processor
    def demo_context():
        return {"public_demo": g.get("public_demo", False)}
