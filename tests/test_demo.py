import unittest
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

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
        self.assertEqual(client.get('/').status_code, 302)
        self.assertEqual(client.post('/demo/entrar').status_code, 302)
        for _ in range(2):
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('Visitante', response.text)
        with app.app_context():
            self.assertEqual(Usuario.query.count(), 0)

    def test_demo_blocks_post_legacy_get_write_and_backup(self):
        app = self.make_app()
        client = app.test_client()
        client.post('/demo/entrar')
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
        response = client.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Acessar como visitante', response.text)
        self.assertIn('name="senha"', response.text)
        self.assertNotIn('NF-DEMO-', response.text)
        client.post('/demo/entrar')
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
        client.get('/auth/logout')
        self.assertEqual(client.get('/').status_code, 302)
        self.assertIn('Acessar como visitante', client.get('/auth/login').text)

    def test_demo_ignores_existing_database_and_seeds_only_synthetic_data(self):
        from app import create_app
        from app.models import Empresa, Item, Tecnico, NotaFiscalEntrada
        with TemporaryDirectory() as directory:
            original = Path(directory) / 'company.db'
            with sqlite3.connect(original) as connection:
                connection.execute('CREATE TABLE private_data (name TEXT)')
                connection.execute("INSERT INTO private_data VALUES ('PRIVATE SENTINEL')")
            connection.close()
            original_bytes = original.read_bytes()
            app = create_app({'TESTING': True, 'SECRET_KEY': 'test',
                              'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + original.as_posix(),
                              'LOGISTOCK_DEMO_PUBLICO': True})
            with app.app_context():
                self.assertNotEqual(Path(db.engine.url.database), original)
                self.assertEqual(Usuario.query.count(), 0)
                self.assertEqual(Item.query.count(), 6)
                self.assertEqual(Tecnico.query.count(), 3)
                self.assertEqual(NotaFiscalEntrada.query.count(), 3)
                self.assertTrue(all('example.invalid' in row.email for row in Empresa.query.all()))
            self.assertEqual(original.read_bytes(), original_bytes)
            self.assertNotIn('PRIVATE SENTINEL', app.test_client().get('/').text)


if __name__ == '__main__':
    unittest.main()
