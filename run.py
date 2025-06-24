from flask import Flask, redirect, url_for, has_request_context
from .extensions import db, login_manager
from flask_migrate import Migrate

# Apenas esta linha fora da função (para registrar os modelos no alembic)
from app import models
from app.models import RequisicaoTecnico
from flask_login import current_user

# Importa todos os comandos CLI do app.cli
from app.cli import init_db, seed_dados, criar_usuario, editar_usuario, listar_usuarios, deletar_usuario

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile('config.py')

    db.init_app(app)
    migrate = Migrate(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # REGISTRA BLUEPRINTS
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
    from app.routes.baixa_campo import bp_baixa
    from app.routes.requisicoes_tecnicos import bp_requisicoes_tecnicos
    from app.routes.auth import auth_bp
    from app.routes.saldo_tecnico import bp as saldo_tecnico_bp

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
    app.register_blueprint(bp_baixa)
    app.register_blueprint(bp_requisicoes_tecnicos)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(saldo_tecnico_bp, url_prefix='/saldo_tecnico')

    # Injeta número de requisições pendentes no contexto global
    @app.context_processor
    def inject_requisicoes_tecnicos_pendentes():
        if has_request_context() and current_user.is_authenticated:
            if current_user.perfil in ['estoque', 'admin']:
                count = RequisicaoTecnico.query.filter_by(status="pendente").count()
                return dict(requisicoes_tecnicos_pendentes=count)
        return dict(requisicoes_tecnicos_pendentes=0)

    @app.route('/')
    def raiz():
        return redirect(url_for('auth.login'))

    return app

# ✅ Para testes locais (opcional)
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8080)
