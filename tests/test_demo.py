import unittest

from flask import Flask
from flask_login import LoginManager, current_user, login_required
from sqlalchemy import text

from app.demo import init_demo
from app.extensions import db
from app.models import Usuario


class PublicDemoTests(unittest.TestCase):
    def make_app(self, enabled=True):
        app = Flask(__name__)
        app.config.update(SECRET_KEY='test', TESTING=True,
                          SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                          LOGISTOCK_DEMO_PUBLICO=enabled)
        db.init_app(app)
        login = LoginManager(app)
        login.user_loader(lambda ident: None)
        init_demo(app)

        @app.get('/')
        @login_required
        def home():
            return current_user.nome

        @app.route('/save', methods=['POST', 'GET'])
        def save():
            db.session.execute(text('INSERT INTO usuarios (nome, email, senha_hash, perfil) '
                                    "VALUES ('Changed', 'bad@example.com', 'x', 'admin')"))
            db.session.commit()
            return 'saved'

        @app.get('/backup/download')
        def backup():
            return 'private'

        with app.app_context():
            db.create_all()
        return app

    def test_automatic_login_persists_without_creating_database_user(self):
        app = self.make_app()
        client = app.test_client()
        for _ in range(2):
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('Visitante', response.text)
        with app.app_context():
            self.assertEqual(Usuario.query.count(), 0)

    def test_demo_blocks_post_legacy_get_write_and_backup(self):
        app = self.make_app()
        client = app.test_client()
        self.assertEqual(client.post('/save').status_code, 403)
        self.assertEqual(client.get('/save').status_code, 403)
        self.assertEqual(client.get('/backup/download').status_code, 403)
        with app.app_context():
            self.assertEqual(Usuario.query.count(), 0)

    def test_disabled_keeps_login_required(self):
        app = self.make_app(enabled=False)
        self.assertEqual(app.test_client().get('/').status_code, 401)

    def test_real_application_opens_dashboard_and_modules_without_login(self):
        from app import create_app
        app = create_app({'TESTING': True, 'SECRET_KEY': 'test',
                          'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                          'LOGISTOCK_DEMO_PUBLICO': True})
        client = app.test_client()
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Demonstração', response.text)
        for endpoint in ('tecnicos.listar_tecnicos',
                         'nota_fiscal.historico'):
            rules = [rule for rule in app.url_map.iter_rules()
                     if rule.endpoint == endpoint and not rule.arguments]
            self.assertTrue(rules, endpoint)
            for rule in rules:
                self.assertEqual(client.get(str(rule)).status_code, 200, str(rule))
        self.assertEqual(client.get('/auth/login').status_code, 302)
        self.assertEqual(client.get('/backup/download').status_code, 403)


if __name__ == '__main__':
    unittest.main()
