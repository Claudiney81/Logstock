import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from browser_fixture import build_app
from app.extensions import db
from app.models import Item, NotaFiscalEntrada, NotaFiscalItem, Estoque, SaldoTecnico


class NoteRegisteredPriceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix='logistock-note-price-')
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

    def save_note(self, kind='empresa', code='TESTE01', submitted_price='999.00'):
        response = self.client.post('/nota/nova', data={
            'numero_nf': 'PRICE-TEST', 'fornecedor': 'Fornecedor Teste',
            'tipo_estoque': kind, 'tipo_servico_id': '1', 'categoria_entrada': 'MATERIAL',
            'cliente_id': '1' if kind == 'cliente' else '',
            'codigo[]': code, 'descricao[]': 'Item teste',
            'quantidade[]': '7', 'valor[]': submitted_price,
        })
        self.assertEqual(response.status_code, 302)
        note = NotaFiscalEntrada.query.filter_by(numero_nf='PRICE-TEST').one()
        return NotaFiscalItem.query.filter_by(nota_fiscal_id=note.id).one()

    def test_company_note_uses_submitted_price_and_quantity(self):
        line = self.save_note()
        self.assertEqual(line.quantidade, 7)
        self.assertEqual(line.valor_unitario, 999.0)
        self.assertEqual(db.session.get(Item, 1).valor, 12.5)
        self.assertTrue(all(stock.valor_unitario == 999.0 for stock in Estoque.query.filter_by(item_id=1).all()))
        self.assertTrue(all(balance.valor_unitario == 999.0 for balance in SaldoTecnico.query.filter_by(item_id=1).all()))

    def test_client_note_preserves_invoice_price(self):
        line = self.save_note(kind='cliente', submitted_price='0.01')
        self.assertEqual(line.valor_unitario, 0.01)
        self.assertEqual(db.session.get(Item, 1).valor, 12.5)

    def test_new_imported_item_keeps_its_initial_registration_price(self):
        line = self.save_note(code='NEW-IMPORT', submitted_price='8.75')
        item = Item.query.filter_by(codigo='NEW-IMPORT').one()
        self.assertEqual(item.valor, 8.75)
        self.assertEqual(line.valor_unitario, 8.75)


if __name__ == '__main__':
    unittest.main()
