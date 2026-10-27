from flask import session
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import Usuario, Tecnico, TipoServico, Item, Estoque, Empresa, OrdemServico, SaldoTecnico, Veiculo


def build_app(database_path):
    app = create_app({
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(database_path).replace('\\', '/'),
        'TESTING': True, 'SECRET_KEY': 'draft-tests-only',
        'SESSION_COOKIE_SECURE': False, 'MAIL_SUPPRESS_SEND': True,
    })
    with app.app_context():
        tecnico = Tecnico(id=1, nome='Tecnico Teste', matricula='teste', cpf='123.456.789-01', email='tecnico@teste.local', status='Ativo')
        tecnico2 = Tecnico(id=2, nome='Outro Tecnico', matricula='outro', cpf='98765432100', email='outro@teste.local')
        admin = Usuario(id=1, nome='Admin Teste', email='admin@teste.local', perfil='admin', senha_hash=generate_password_hash('teste'))
        user = Usuario(id=2, nome=tecnico.nome, email=tecnico.email, tecnico_id=1, perfil='tecnico', senha_hash=generate_password_hash('senha-original'))
        tipo = TipoServico(id=1, nome='Instalacao', tipo_estoque='empresa')
        cliente = Empresa(id=1, razao_social='Cliente Teste', cnpj='12345678901234', tipo_empresa='cliente')
        db.session.add(Empresa(id=2, razao_social='Fornecedor Teste', cnpj='12345678901235', tipo_empresa='fornecedor'))
        db.session.add_all([tecnico, tecnico2, admin, user, tipo, cliente])
        db.session.flush()
        item = Item(id=1, codigo='TESTE01', descricao='Cabo teste', unidade='UN', valor=12.5, categoria='MATERIAL', tipo_servico_id=1)
        item2 = Item(id=2, codigo='TESTE02', descricao='Conector teste', unidade='UN', valor=5, categoria='MATERIAL', tipo_servico_id=1)
        db.session.add_all([item,item2])
        db.session.add(Item(id=3, codigo='FERR01', descricao='Alicate teste', unidade='UN', valor=30, categoria='FERRAMENTA', tipo_servico_id=1))
        db.session.add(Usuario(id=3, nome='Outro Admin', email='admin3@teste.local', perfil='admin', senha_hash=generate_password_hash('teste')))
        db.session.add(Veiculo(id=1, placa='TEST123', marca='Teste', modelo='Carro Teste'))
        db.session.add(OrdemServico(id=1, numero_os='OS001', cliente_id=1, tipo_servico_id=1, endereco='Rua Teste'))
        db.session.flush()
        db.session.add_all([Estoque(item_id=i, tipo_servico_id=1, quantidade=100, tipo_estoque='empresa', valor_unitario=12.5) for i in [1,2]])
        db.session.add(Estoque(item_id=3, tipo_servico_id=1, quantidade=50, tipo_estoque='empresa', valor_unitario=30))
        db.session.add_all([SaldoTecnico(tecnico_id=1, item_id=i, tipo_servico_id=1, quantidade=50, tipo_estoque='empresa', valor_unitario=12.5) for i in [1,2]])
        db.session.commit()

    @app.get('/__test/login/<int:user>')
    def test_login(user):
        session.clear()
        session['_user_id'] = str(user)
        session['_fresh'] = True
        if user == 2:
            session['tecnico_id'] = 1
            session['perfil_mobile'] = 'tecnico'
        return 'ok'

    return app
