import io
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from browser_fixture import build_app
from app.extensions import db
from app.models import Estoque, TipoServico
from app.routes.estoque import buscar_alertas_estoque


class EstoqueMinimosTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        with patch.dict(os.environ, {'LOGISTOCK_ADMIN_EMAIL': '', 'LOGISTOCK_ADMIN_PASSWORD': ''}):
            self.app = build_app(Path(self.directory.name, 'test.db'))
        self.context = self.app.app_context()
        self.context.push()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = '1'
            session['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()
        self.directory.cleanup()

    def test_save_reload_red_alert_and_both_excel_exports(self):
        response = self.client.post('/estoque/atualizar_minimos', data={
            'tipo_estoque': 'empresa', 'minimos[1]': '120',
        })
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertEqual(Estoque.query.filter_by(item_id=1).one().quantidade_minima, 120)
        html = self.client.get(response.location).get_data(as_text=True)
        self.assertIn('value="120"', html)
        self.assertIn('text-danger fw-bold', html)
        self.assertEqual(len(buscar_alertas_estoque()), 1)
        for path, sheet, header in [
            ('/estoque/alertas/exportar_excel', 'Estoque Baixo', 0),
            ('/estoque/exportar_criticos', 'Alerta Pedido', 3),
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            frame = pd.read_excel(io.BytesIO(response.data), sheet_name=sheet, header=header)
            self.assertEqual(frame.iloc[0]['Código'], 'TESTE01')
            self.assertEqual(frame.iloc[0]['Quantidade Atual'], 100)
            self.assertEqual(frame.iloc[0]['Quantidade a Comprar'], 20)

    def test_aggregate_available_stock_excludes_defects_and_zero_minimum(self):
        stock = Estoque.query.filter_by(item_id=1).one()
        stock.quantidade = 3
        stock.quantidade_minima = 10
        db.session.add_all([
            Estoque(item_id=1, tipo_estoque='empresa', tipo_servico_id=1,
                    quantidade=8, quantidade_minima=10, condicao_material='DISPONIVEL'),
            Estoque(item_id=1, tipo_estoque='empresa', tipo_servico_id=1,
                    quantidade=50, quantidade_minima=10, condicao_material='NOVO_DEF'),
        ])
        other = Estoque.query.filter_by(item_id=2).one()
        other.quantidade = 0
        other.quantidade_minima = 0
        db.session.commit()
        self.assertEqual(buscar_alertas_estoque(), [])
        stock.quantidade = 0
        db.session.commit()
        alerts = buscar_alertas_estoque()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0].quantidade, 8)

    def test_service_filter_and_empty_stock_persist(self):
        db.session.add(TipoServico(id=2, nome='Manutencao', tipo_estoque='empresa'))
        stock = Estoque.query.filter_by(item_id=1).one()
        stock.tipo_servico_id = 2
        stock.quantidade = 0
        db.session.commit()
        self.client.post('/estoque/atualizar_minimos', data={
            'tipo_estoque': 'empresa', 'tipo_servico_id': '2', 'minimos[1]': '20',
        })
        self.assertEqual(len(buscar_alertas_estoque(2)), 1)
        self.assertEqual(buscar_alertas_estoque(1), [])
        html = self.client.get('/estoque/saldo?tipo_estoque=empresa&tipo_servico_id=2').get_data(as_text=True)
        self.assertIn('value="20"', html)


if __name__ == '__main__':
    unittest.main()
