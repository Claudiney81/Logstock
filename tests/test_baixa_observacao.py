import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import test_estoque_minimos
from app.extensions import db
from app.models import BaixaTecnica, BaixaTecnicaItem


class BaixaObservacaoTests(unittest.TestCase):
    setUp = test_estoque_minimos.EstoqueMinimosTests.setUp
    tearDown = test_estoque_minimos.EstoqueMinimosTests.tearDown

    def test_mobile_correction_preserves_observation_and_allows_real_edit(self):
        original = 'Instalação realizada. Sistema com 12 painéis de 625W.'
        for submitted in (None, '', '   ', 'N/D', 'Observação complementada pelo técnico.'):
            with self.subTest(submitted=submitted):
                baixa = BaixaTecnica(tecnico_id=1, tipo_servico_id=1,
                                     cliente_id=1, ordem_servico_id=1,
                                     origem_mobile=True, status='pendente', observacao=original)
                db.session.add(baixa)
                db.session.flush()
                db.session.add(BaixaTecnicaItem(baixa_tecnica_id=baixa.id,
                                              item_id=1, tipo_estoque='empresa',
                                              quantidade=2, status='pendente'))
                db.session.commit()
                response = self.client.post(f'/baixa_desktop/detalhe/{baixa.id}',
                                            data={'recusar': '1', 'motivo': 'Corrigir quantidade'})
                self.assertEqual(response.status_code, 302)
                db.session.refresh(baixa)
                self.assertEqual(baixa.observacao, original)
                data = {'tecnico_id': '1', 'tipo_servico_id': '1', 'cliente_id': '1',
                        'ordem_servico_id': '1', 'baixa_id_corrigir': str(baixa.id),
                        'item_id[]': '1', 'quantidade[]': '3',
                        'tipo_estoque[]': 'empresa', 'cliente_estoque_id[]': ''}
                if submitted is not None:
                    data['observacao'] = submitted
                response = self.client.post('/baixa_tecnico/registrar', data=data)
                self.assertEqual(response.status_code, 302)
                db.session.refresh(baixa)
                self.assertEqual(baixa.status, 'revisada')
                expected = submitted if submitted and submitted.strip() and submitted != 'N/D' else original
                self.assertEqual(baixa.observacao, expected)
                html = self.client.get(f'/baixa_desktop/detalhe/{baixa.id}').get_data(as_text=True)
                self.assertIn(expected, html)


if __name__ == '__main__':
    unittest.main()
