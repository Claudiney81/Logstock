# app/__init__.py

from flask import Flask, redirect, url_for, has_request_context, session, render_template, request, flash
from .extensions import db, login_manager, mail
from flask_migrate import Migrate
from app.models import RequisicaoTecnico, Usuario
from flask_login import current_user
from werkzeug.security import check_password_hash
from app.routes.ferramentas_epis import bp_ferramentas_epis
from app.routes.frota_vistoria import bp_frota_vistoria
import os


# Comandos CLI
from app.cli import (
    init_db,
    seed_dados,
    criar_usuario,
    editar_usuario,
    listar_usuarios,
    deletar_usuario
)


def _import_bp(module_path, candidates=('bp', 'bp_estoque', 'estoque_bp', 'bp_routes', 'blueprint')):
    mod = __import__(module_path, fromlist=['*'])

    for name in candidates:
        if hasattr(mod, name):
            return getattr(mod, name)

    raise ImportError(
        f"Blueprint variável não encontrada em {module_path}. "
        f"Esperado um dos nomes: {candidates}"
    )


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "config.py"
    )

    app.config.from_pyfile(config_path)

    db.init_app(app)
    mail.init_app(app)

    from app import models  # noqa: F401

    with app.app_context():
        db.create_all()

    from werkzeug.security import generate_password_hash

    if not Usuario.query.filter_by(
        email="claudineymoura@gmail.com"
    ).first():

        usuario = Usuario(
            nome="Claudiney Moura",
            email="claudineymoura@gmail.com",
            senha_hash=generate_password_hash("123456"),
            perfil="admin"
        )

        db.session.add(usuario)
        db.session.commit()
        

    Migrate(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return Usuario.query.get(int(user_id))
        except Exception:
            return None

    estoque_bp = _import_bp('app.routes.estoque')

    nota_fiscal_bp = _import_bp('app.routes.nota_fiscal')

    empresas_bp = _import_bp(
        'app.routes.empresas',
        candidates=('empresas_bp', 'bp', 'blueprint')
    )

    itens_bp = _import_bp(
        'app.routes.itens',
        candidates=('bp', 'itens_bp')
    )

    tipo_servico_bp = _import_bp(
        'app.routes.tipo_servico',
        candidates=('tipo_servico_bp', 'bp')
    )

    home_bp = _import_bp(
        'app.routes.home',
        candidates=('home_bp', 'bp')
    )

    tecnicos_bp = _import_bp(
        'app.routes.tecnicos',
        candidates=('bp', 'tecnicos_bp')
    )

    bp_baixa_desktop = _import_bp(
        'app.routes.baixa_desktop',
        candidates=('bp_baixa_desktop', 'bp')
    )

    bp_requisicoes_tecnicos = _import_bp(
        'app.routes.requisicoes_tecnicos',
        candidates=('bp_requisicoes_tecnicos', 'bp')
    )

    bp_requisicao_mobile = _import_bp(
        'app.routes.requisicao_mobile',
        candidates=('bp_requisicao_mobile', 'bp')
    )

    auth_bp = _import_bp(
        'app.routes.auth',
        candidates=('auth_bp', 'bp')
    )

    saldo_tecnico_bp = _import_bp(
        'app.routes.saldo_tecnico',
        candidates=('bp', 'saldo_tecnico_bp')
    )

    bp_inventario = _import_bp(
        'app.routes.inventario_tecnico',
        candidates=('bp_inventario', 'bp')
    )

    bp_baixa_tecnico = _import_bp(
        'app.routes.baixa_tecnico',
        candidates=('bp_baixa_tecnico', 'bp')
    )

    inventario_estoque_bp = _import_bp(
        'app.routes.inventario_estoque',
        candidates=('bp', 'inventario_estoque_bp')
    )

    bp_login_supervisor = _import_bp(
        'app.routes.login_supervisor',
        candidates=('bp_login_supervisor', 'bp')
    )

    bp_equipamentos = _import_bp(
        'app.routes.equipamentos',
        candidates=('bp_equipamentos', 'bp')
    )

    bp_tecnico_mobile = _import_bp(
        'app.routes.tecnico_mobile',
        candidates=('bp_tecnico_mobile', 'bp')
    )

    bp_movimentacao = _import_bp(
        'app.routes.movimentacao_estoque',
        candidates=('bp_movimentacao', 'bp')
    )

    bp_frota = _import_bp(
        'app.routes.frota',
        candidates=('frota_bp', 'bp')
    )

    app.register_blueprint(estoque_bp)
    app.register_blueprint(nota_fiscal_bp)
    app.register_blueprint(bp_frota)
    app.register_blueprint(bp_frota_vistoria)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(itens_bp)

    app.register_blueprint(
        tipo_servico_bp,
        url_prefix='/cadastro'
    )

    app.register_blueprint(home_bp)
    app.register_blueprint(tecnicos_bp)

    app.register_blueprint(
        bp_baixa_desktop,
        url_prefix='/baixa_desktop'
    )

    app.register_blueprint(bp_requisicoes_tecnicos)
    app.register_blueprint(bp_ferramentas_epis)

    app.register_blueprint(
        bp_requisicao_mobile,
        url_prefix='/requisicao_mobile'
    )

    app.register_blueprint(
        auth_bp,
        url_prefix='/auth'
    )

    app.register_blueprint(
        saldo_tecnico_bp,
        url_prefix='/saldo_tecnico'
    )

    app.register_blueprint(bp_inventario)
    app.register_blueprint(inventario_estoque_bp)
    app.register_blueprint(bp_login_supervisor)

    app.register_blueprint(
        bp_baixa_tecnico,
        url_prefix='/baixa_tecnico'
    )

    app.register_blueprint(
        bp_equipamentos,
        url_prefix="/equipamentos"
    )

    app.register_blueprint(bp_tecnico_mobile)
    app.register_blueprint(bp_movimentacao)

    app.cli.add_command(init_db)
    app.cli.add_command(seed_dados)
    app.cli.add_command(criar_usuario)
    app.cli.add_command(editar_usuario)
    app.cli.add_command(listar_usuarios)
    app.cli.add_command(deletar_usuario)

    @app.context_processor
    def inject_requisicoes_tecnicos_pendentes():
        try:
            if has_request_context() and current_user.is_authenticated:
                if (
                    hasattr(current_user, 'perfil')
                    and current_user.perfil in ['estoque', 'admin']
                ):
                    count = RequisicaoTecnico.query.filter_by(
                        status="pendente"
                    ).count()

                    return dict(
                        requisicoes_tecnicos_pendentes=count
                    )

        except Exception:
            pass

        return dict(
            requisicoes_tecnicos_pendentes=0
        )

    @app.route('/')
    def raiz():
        return redirect(url_for('auth.login'))

    @app.route("/login-tecnico", methods=["GET", "POST"])
    def login_tecnico():

        if request.method == "POST":

            email = request.form.get("email")
            senha = request.form.get("senha")

            usuario = Usuario.query.filter_by(
                email=email,
                perfil="tecnico"
            ).first()

            if usuario and check_password_hash(
                usuario.senha_hash,
                senha
            ):

                session.permanent = True

                session["usuario_id"] = usuario.id
                session["tecnico_id"] = usuario.id
                session["tecnico_nome"] = usuario.nome
                session["perfil"] = usuario.perfil

                return redirect(
                    url_for("baixa_tecnico.formulario_baixa")
                )

            flash(
                "Email ou senha inválidos",
                "danger"
            )

        return render_template(
            "baixa_tecnico/login_tecnico.html"
        )

    @app.template_filter('brl')
    def brl_format(value):

        try:
            return (
                f"R$ {value:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )

        except (ValueError, TypeError):
            return "R$ 0,00"

    return app