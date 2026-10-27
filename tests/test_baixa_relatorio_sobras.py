import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_estoque_minimos import EstoqueMinimosTests
from app.extensions import db
from app.models import BaixaTecnica, BaixaTecnicaItem, MovimentacaoEstoque, MovimentacaoEstoqueItem
from app.routes.baixa_desktop import grupos_relatorio_baixa
from openpyxl import load_workbook


class RelatorioSobrasTests(unittest.TestCase):
    setUp = EstoqueMinimosTests.setUp
    tearDown = EstoqueMinimosTests.tearDown

    def test_exports_historical_surplus_without_increasing_applied_total(self):
        baixa = BaixaTecnica(tecnico_id=1, tipo_servico_id=1, cliente_id=1,
                             ordem_servico_id=1, status='confirmado')
        db.session.add(baixa)
        db.session.flush()
        for origem in ('cliente', 'empresa'):
            db.session.add(BaixaTecnicaItem(baixa_tecnica_id=baixa.id, item_id=1,
                tipo_estoque=origem, quantidade=2, valor_unitario=10, valor_total=20))
        for tecnico, os_id, tipo, quantidade in (
            (1, 1, 'retorno_sobra_os', 3),
            (2, 1, 'retorno_sobra_os', 99),
            (1, None, 'retorno_sobra_os', 88),
            (1, 1, 'retorno', 77),
        ):
            mov = MovimentacaoEstoque(origem_tipo='cliente', origem_id=1,
                destino_tipo='tecnico', destino_id=tecnico, ordem_servico_id=os_id,
                tipo_movimentacao=tipo)
            mov.itens.append(MovimentacaoEstoqueItem(item_id=2, quantidade=quantidade,
                                                     valor_unitario=5))
            db.session.add(mov)
        db.session.commit()
        self.assertEqual([i.quantidade for i in grupos_relatorio_baixa(baixa)['sobra']], [3])
        response = self.client.get(f'/baixa_desktop/detalhe/{baixa.id}/excel')
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(io.BytesIO(response.data)).active
        rows = list(sheet.values)
        self.assertTrue(any(r[0] and str(r[0]).startswith('SOBRA DO MATERIAL') for r in rows))
        sobra = next(r for r in rows if r[0] == 'TESTE02')
        self.assertEqual(sobra[3:6], (3, 5, 15))
        total = next(r for r in rows if r[0] == 'TOTAL GERAL DA BAIXA')
        self.assertEqual(total[4], 40)
        response = self.client.get(f'/baixa_desktop/detalhe/{baixa.id}/pdf')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'%PDF'))

    def test_no_os_does_not_include_general_technician_stock(self):
        baixa = BaixaTecnica(tecnico_id=1, tipo_servico_id=1)
        self.assertEqual(grupos_relatorio_baixa(baixa)['sobra'], [])


if __name__ == '__main__':
    unittest.main()
