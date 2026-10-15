"""Run with python -m unittest discover -s tests -p 'test_*.py'."""
import unittest
from unittest.mock import patch

from flask import Flask, flash, redirect
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

from app.drafts import init_drafts, draft_saved
from app.extensions import db
from app.models import Tecnico, Usuario
from app.routes.tecnicos import bp


class DraftAndTechnicianTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY='tests-only',
                               SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(self.app)
        login = LoginManager(self.app)
        login.user_loader(lambda ident: db.session.get(Usuario, int(ident)))
        self.app.register_blueprint(bp)
        init_drafts(self.app)

        @self.app.post('/operation/<result>')
        def operation(result):
            flash('result', result)
            return redirect('/done')

        @self.app.post('/committed-warning')
        def committed_warning():
            flash('Saved with a warning', 'warning')
            draft_saved()
            return redirect('/done')

        @self.app.get('/context-only')
        def context_only():
            context = {}
            self.app.update_template_context(context)
            return 'Context built without rendering the draft script'

        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        tecnico = Tecnico(id=1, nome='Original', matricula='original', cpf='123.456.789-01',
                          email='original@example.com', status='Ativo')
        outro = Tecnico(id=2, nome='Outro', matricula='outro', cpf='98765432100', email='outro@example.com')
        self.password = generate_password_hash('unchanged')
        db.session.add_all([tecnico, outro,
            Usuario(id=1, nome='Admin', email='admin@example.com', perfil='admin', senha_hash=self.password),
            Usuario(id=2, nome='Original', email=tecnico.email, perfil='tecnico', tecnico_id=1, senha_hash=self.password)])
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = '1'
            session['_fresh'] = True
        self.data = dict(nome='Atualizado', matricula='atualizado', cpf='12345678901',
                         email='novo@example.com', telefone='11999999999', funcao='Instalador', status='Ativo')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_only_confirmed_success_completes_draft(self):
        key = 'logistock:draft:v1:usuario-1:/operation:0'
        for category in ('danger', 'warning', 'info'):
            self.client.post('/operation/' + category, data={'_draft_key': key})
            with self.client.session_transaction() as session:
                self.assertNotIn('_completed_drafts', session)
        self.client.post('/operation/success', data={'_draft_key': key})
        with self.client.session_transaction() as session:
            self.assertEqual(session['_completed_drafts'], [key])

    def test_invalid_key_is_not_stored(self):
        for key in ('untrusted', 'logistock:draft:v1:usuario-2:/operation:0', 'logistock:draft:v1:anon-other:/operation:0'):
            self.client.post('/operation/success', data={'_draft_key': key})
            with self.client.session_transaction() as session:
                self.assertNotIn('_completed_drafts', session)

    def test_authenticated_submission_can_finish_its_own_prelogin_work(self):
        with self.client.session_transaction() as session:
            session['_draft_anonymous_id'] = 'this-session-only'
        key = 'logistock:draft:v1:anon-this-session-only:/operation:0'
        self.client.post('/operation/success', data={'_draft_key': key})
        with self.client.session_transaction() as session:
            self.assertEqual(session['_completed_drafts'], [key])

    def test_committed_warning_can_complete_draft(self):
        key = 'logistock:draft:v1:usuario-1:/operation:0'
        self.client.post('/committed-warning', data={'_draft_key': key})
        with self.client.session_transaction() as session:
            self.assertEqual(session['_completed_drafts'], [key])

    def test_other_template_contexts_do_not_consume_confirmation(self):
        key = 'logistock:draft:v1:usuario-1:/operation:0'
        self.client.post('/operation/success', data={'_draft_key': key})
        self.client.get('/context-only')
        with self.client.session_transaction() as session:
            self.assertEqual(session['_completed_drafts'], [key])

    def test_edit_preserves_identity_password_and_link(self):
        response = self.client.post('/tecnicos/editar/1', data=self.data)
        self.assertEqual(response.status_code, 302)
        tecnico = db.session.get(Tecnico, 1)
        usuario = db.session.get(Usuario, 2)
        self.assertEqual(tecnico.nome, 'Atualizado')
        self.assertEqual(tecnico.cpf, '123.456.789-01')
        self.assertEqual(usuario.email, self.data['email'])
        self.assertEqual(usuario.nome, self.data['nome'])
        self.assertEqual(usuario.tecnico_id, 1)
        self.assertEqual(usuario.senha_hash, self.password)
        self.assertEqual(usuario.perfil, 'tecnico')

    def test_conflicts_leave_both_records_unchanged(self):
        for changes in ({'cpf': '987.654.321-00'}, {'matricula': 'outro'},
                        {'email': 'admin@example.com'}, {'email': 'outro@example.com'},
                        {'email': ''}, {'cpf': '1'}, {'status': 'invalido'}):
            with self.subTest(changes=changes), patch('app.routes.tecnicos.render_template', return_value='invalid'):
                response = self.client.post('/tecnicos/editar/1', data=self.data | changes)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(db.session.get(Tecnico, 1).nome, 'Original')
                self.assertEqual(db.session.get(Usuario, 2).email, 'original@example.com')

    def test_only_staff_can_edit(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '2'
        self.assertEqual(self.client.post('/tecnicos/editar/1', data=self.data).status_code, 403)
        self.assertEqual(db.session.get(Tecnico, 1).nome, 'Original')

    def test_anonymous_cannot_edit(self):
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.post('/tecnicos/editar/1', data=self.data).status_code, 401)


if __name__ == '__main__':
    unittest.main()
