from flask import Flask, redirect, url_for, has_request_context, session, render_template, request, flash
from .extensions import db, login_manager
from flask_migrate import Migrate
from app.models import RequisicaoTecnico, Usuario
from flask_login import current_user
from werkzeug.security import check_password_hash

# Comandos CLI
from app.cli import init_db, seed_dados, criar_usuario, editar_usuario, listar_usuarios, deletar_usuario

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile('config.py')

    db.init_app(app)

    # Importa todos os modelos para o Alembic reconhecer
    from app import models

    migrate = Migrate(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Blueprints
    from app.routes import estoque
    from app.routes import nota_fiscal
    from app.routes.empresas import empresas_bp
    from app.routes.transferencias.externa import bp_externa
    from app.routes.transferencias.interna import bp_interna
    from app.routes.itens import bp as itens_bp
    from app.routes.tipo_servico import tipo_servico_bp
    from app.routes.home import home_bp
    from app.routes import tecnicos
    from app.routes.kit_inicial import kit_inicial_bp
    from app.routes.baixa_desktop import bp_baixa_desktop
    from app.routes.requisicoes_tecnicos import bp_requisicoes_tecnicos
    from app.routes.auth import auth_bp
    from app.routes.saldo_tecnico import bp as saldo_tecnico_bp
    from app.routes.inventario_tecnico import bp_inventario
    from app.routes.baixa_tecnico import bp_baixa_tecnico
    from app.routes.inventario_estoque import bp as inventario_estoque_bp
    from app.routes.login_supervisor import bp_login_supervisor
    from app.routes.equipamentos import bp_equipamentos


    # Registro dos Blueprints
    app.register_blueprint(estoque.bp)
    app.register_blueprint(nota_fiscal.bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(bp_externa)
    app.register_blueprint(bp_interna)
    app.register_blueprint(itens_bp)
    app.register_blueprint(tipo_servico_bp, url_prefix='/cadastro')
    app.register_blueprint(home_bp)
    app.register_blueprint(tecnicos.bp)
    app.register_blueprint(kit_inicial_bp, url_prefix='/kit_inicial')
    app.register_blueprint(bp_baixa_desktop, url_prefix='/baixa_desktop')
    app.register_blueprint(bp_requisicoes_tecnicos)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(saldo_tecnico_bp, url_prefix='/saldo_tecnico')
    app.register_blueprint(bp_inventario)
    app.register_blueprint(inventario_estoque_bp)
    app.register_blueprint(bp_login_supervisor, url_prefix='/login-supervisor')
    app.register_blueprint(bp_baixa_tecnico, url_prefix='/baixa_tecnico')
    app.register_blueprint(bp_equipamentos, url_prefix="/equipamentos")

    # Comandos CLI
    app.cli.add_command(init_db)
    app.cli.add_command(seed_dados)
    app.cli.add_command(criar_usuario)
    app.cli.add_command(editar_usuario)
    app.cli.add_command(listar_usuarios)
    app.cli.add_command(deletar_usuario)

    # Injeta o número de requisições técnicas pendentes no contexto global
    @app.context_processor
    def inject_requisicoes_tecnicos_pendentes():
        try:
            if has_request_context() and current_user.is_authenticated:
                if hasattr(current_user, 'perfil') and current_user.perfil in ['estoque', 'admin']:
                    count = RequisicaoTecnico.query.filter_by(status="pendente").count()
                    return dict(requisicoes_tecnicos_pendentes=count)
        except:
            pass
        return dict(requisicoes_tecnicos_pendentes=0)

    # Redireciona a raiz para login
    @app.route('/')
    def raiz():
        return redirect(url_for('auth.login'))

        # Login simplificado para perfil técnico
    @app.route("/login-tecnico", methods=["GET", "POST"])
    def login_tecnico():
        if request.method == "POST":
            email = request.form.get("email")
            senha = request.form.get("senha")

            usuario = Usuario.query.filter_by(email=email, perfil="tecnico").first()

            if usuario and check_password_hash(usuario.senha_hash, senha):
                session.permanent = True
                session["usuario_id"] = usuario.id
                session["tecnico_id"] = usuario.id
                session["tecnico_nome"] = usuario.nome
                session["perfil"] = usuario.perfil
                return redirect(url_for("baixa_tecnico.formulario_baixa"))
            else:
                flash("Email ou senha inválidos", "danger")

        return render_template("baixa_tecnico/login_tecnico.html")

    # --- Filtro BRL para exibir valores no formato brasileiro ---
    @app.template_filter('brl')
    def brl_format(value):
        try:
            return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (ValueError, TypeError):
            return "R$ 0,00"

    return app
