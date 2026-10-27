import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import test_estoque_minimos as fixtures
from app.extensions import db
from app.models import (Empresa, Estoque, MovimentacaoEstoque, NotaFiscalEntrada,
                        NotaFiscalItem, OrdemServico, SaldoTecnico, MovimentacaoEstoqueItem)
from openpyxl import load_workbook


class RetornoMaterialClienteTests(unittest.TestCase):
    setUp = fixtures.EstoqueMinimosTests.setUp
    tearDown = fixtures.EstoqueMinimosTests.tearDown

    def preparar(self):
        db.session.add(Empresa(id=3, razao_social='Outro Cliente', cnpj='12345678901236', tipo_empresa='cliente'))
        db.session.add(OrdemServico(id=2, numero_os='OS002', cliente_id=1, tipo_servico_id=1))
        db.session.add(OrdemServico(id=3, numero_os='OS003', cliente_id=3, tipo_servico_id=1))
        db.session.flush()
        self.saldo = SaldoTecnico(tecnico_id=1, item_id=1, tipo_servico_id=1,
            tipo_estoque='cliente', cliente_id=1, ordem_servico_id=1,
            quantidade=10, valor_unitario=2)
        self.estoque = Estoque(item_id=1, tipo_servico_id=1, tipo_estoque='cliente',
                               cliente_id=1, quantidade=3, valor_unitario=8)
        self.outros = [
            SaldoTecnico(tecnico_id=2, item_id=1, tipo_servico_id=1, tipo_estoque='cliente', cliente_id=1, ordem_servico_id=1, quantidade=20),
            SaldoTecnico(tecnico_id=1, item_id=1, tipo_servico_id=1, tipo_estoque='cliente', cliente_id=1, ordem_servico_id=2, quantidade=20),
            SaldoTecnico(tecnico_id=1, item_id=1, tipo_servico_id=1, tipo_estoque='cliente', cliente_id=3, ordem_servico_id=3, quantidade=20),
        ]
        db.session.add_all([self.saldo, self.estoque] + self.outros)
        db.session.commit()

    def dados(self, **changes):
        data = {'origem_tipo': 'tecnico', 'destino_tipo': 'cliente',
            'saldo_tecnico_tipo': 'cliente', 'categoria_movimentacao': 'MATERIAL',
            'tecnico_id': '1', 'cliente_id': '1', 'ordem_servico_id': '1',
            'tipo_servico_id': '1', 'codigo[]': ['TESTE01'], 'quantidade[]': ['10'],
            'valor_unitario[]': ['999'], 'quantidade_minima[]': ['0'],
            'observacao': 'Retorno para corrigir origem da nota'}
        data.update(changes)
        return data

    def enviar(self, data=None):
        with patch('app.routes.movimentacao_estoque.send_movimentacao_email', return_value=False):
            result = self.client.post('/movimentacao_estoque/nova', data=data or self.dados())
        db.session.expire_all()
        self.assertEqual(result.status_code, 302)
        return result

    def conferir_inalterado(self):
        self.assertEqual(self.saldo.quantidade, 10)
        self.assertEqual(self.estoque.quantidade, 3)
        self.assertEqual(MovimentacaoEstoque.query.count(), 0)

    def test_return_then_cancel_invoice_preserves_unrelated_stock(self):
        self.preparar()
        nota = NotaFiscalEntrada(numero_nf='NF-RETORNO', fornecedor='Fornecedor Teste',
            tipo_estoque='cliente', cliente_id=1, tipo_servico_id=1)
        nota.itens.append(NotaFiscalItem(item_id=1, quantidade=10, valor_unitario=2))
        db.session.add(nota)
        db.session.commit()
        self.enviar()
        self.assertEqual(self.saldo.quantidade, 0)
        self.assertEqual(self.estoque.quantidade, 13)
        self.assertEqual(self.estoque.valor_unitario, 8)
        self.assertEqual([s.quantidade for s in self.outros], [20, 20, 20])
        empresa = Estoque.query.filter_by(item_id=1, tipo_estoque='empresa').one()
        self.assertEqual(empresa.quantidade, 100)
        mov = MovimentacaoEstoque.query.one()
        self.assertEqual((mov.origem_tipo, mov.origem_id, mov.destino_tipo, mov.destino_id), ('tecnico', 1, 'cliente', 1))
        self.assertEqual(mov.tipo_movimentacao, 'retorno_cliente')
        self.assertEqual((mov.itens[0].quantidade, mov.itens[0].valor_unitario), (10, 2))
        self.client.post(f'/nota/excluir/{nota.id}')
        db.session.expire_all()
        self.assertIn('[NF_CANCELADA]', nota.observacao)
        self.assertEqual(self.estoque.quantidade, 3)
        self.assertEqual(empresa.quantidade, 100)
        self.assertEqual([s.quantidade for s in self.outros], [20, 20, 20])

    def criar_nota_transferida(self, numero='NF-CICLO', quantidade=10):
        nota = NotaFiscalEntrada(numero_nf=numero, fornecedor='Teste',
            tipo_estoque='cliente', cliente_id=1, tipo_servico_id=1)
        nota.itens.append(NotaFiscalItem(item_id=1, quantidade=quantidade, valor_unitario=2))
        db.session.add(nota)
        db.session.flush()
        mov = MovimentacaoEstoque(origem_tipo='cliente', origem_id=1,
            destino_tipo='tecnico', destino_id=1, tipo_servico_id=1,
            ordem_servico_id=1, nota_fiscal_id=nota.id)
        mov.itens.append(MovimentacaoEstoqueItem(item_id=1, quantidade=quantidade, valor_unitario=2))
        db.session.add(mov)
        db.session.commit()
        return nota

    def notas_disponiveis(self):
        return self.client.get('/movimentacao_estoque/api/notas-cliente?cliente_id=1&tipo_servico_id=1&ordem_servico_id=1').get_json()

    def test_return_releases_invoice_and_retransfer_consumes_credit(self):
        self.preparar()
        nota = self.criar_nota_transferida()
        self.assertEqual(self.notas_disponiveis(), [])
        self.enviar(self.dados(**{'quantidade[]': ['4']}))
        self.assertEqual(self.notas_disponiveis()[0]['total_pendente'], 4)
        self.enviar(self.dados(origem_tipo='cliente', destino_tipo='tecnico',
            nota_fiscal_id=str(nota.id), **{'quantidade[]': ['4']}))
        self.assertEqual(self.saldo.quantidade, 10)
        self.assertEqual(self.estoque.quantidade, 3)
        self.assertEqual(self.notas_disponiveis(), [])

    def test_full_return_then_cancel_removes_invoice_stock_once(self):
        self.preparar()
        nota = self.criar_nota_transferida()
        self.enviar()
        self.assertEqual(self.notas_disponiveis()[0]['total_pendente'], 10)
        self.client.post(f'/nota/excluir/{nota.id}')
        db.session.expire_all()
        self.assertEqual(self.estoque.quantidade, 3)
        self.assertEqual(self.saldo.quantidade, 0)
        self.assertEqual(self.notas_disponiveis(), [])
        self.client.post(f'/nota/excluir/{nota.id}')
        db.session.expire_all()
        self.assertEqual(self.estoque.quantidade, 3)

    def test_return_cannot_credit_multiple_invoices(self):
        self.preparar()
        primeira = self.criar_nota_transferida('NF-A')
        self.criar_nota_transferida('NF-B')
        self.enviar(self.dados(**{'quantidade[]': ['4']}))
        self.assertEqual([(n['id'], n['total_pendente']) for n in self.notas_disponiveis()], [(primeira.id, 4)])

    def test_cancel_after_full_return_zeros_stock_when_no_other_entry_exists(self):
        self.preparar()
        self.estoque.quantidade = 0
        db.session.commit()
        nota = self.criar_nota_transferida()
        self.enviar()
        self.assertEqual(self.estoque.quantidade, 10)
        self.client.post(f'/nota/excluir/{nota.id}')
        db.session.expire_all()
        self.assertIn('[NF_CANCELADA]', nota.observacao)
        self.assertEqual(self.estoque.quantidade, 0)
        self.assertEqual(self.saldo.quantidade, 0)
        self.assertEqual(self.notas_disponiveis(), [])
        params = (f'/movimentacao_estoque/api/itens?origem_tipo=cliente'
                  f'&cliente_id=1&tipo_servico_id=1&ordem_servico_id=1'
                  f'&nota_fiscal_id={nota.id}')
        self.assertEqual(self.client.get(params).get_json(), [])
        self.enviar(self.dados(origem_tipo='cliente', destino_tipo='tecnico',
            nota_fiscal_id=str(nota.id), **{'quantidade[]': ['1']}))
        self.assertEqual(self.estoque.quantidade, 0)
        self.assertEqual(self.saldo.quantidade, 0)

    def test_other_technician_or_os_return_does_not_release_invoice(self):
        self.preparar()
        self.criar_nota_transferida()
        self.enviar(self.dados(tecnico_id='2', **{'quantidade[]': ['4']}))
        self.enviar(self.dados(ordem_servico_id='2', **{'quantidade[]': ['4']}))
        self.assertEqual(self.notas_disponiveis(), [])

    def test_return_before_transfer_cannot_credit_future_transfer(self):
        self.preparar()
        self.enviar()
        self.criar_nota_transferida()
        self.assertEqual(self.notas_disponiveis(), [])

    def test_retransfer_above_return_or_available_stock_is_blocked(self):
        self.preparar()
        nota = self.criar_nota_transferida()
        self.enviar(self.dados(**{'quantidade[]': ['4']}))
        self.enviar(self.dados(origem_tipo='cliente', destino_tipo='tecnico',
            nota_fiscal_id=str(nota.id), **{'quantidade[]': ['5']}))
        self.assertEqual(self.saldo.quantidade, 6)
        self.assertEqual(self.estoque.quantidade, 7)
        self.estoque.quantidade = 2
        db.session.commit()
        self.assertEqual(self.notas_disponiveis()[0]['total_pendente'], 2)
        self.enviar(self.dados(origem_tipo='cliente', destino_tipo='tecnico',
            nota_fiscal_id=str(nota.id), **{'quantidade[]': ['3']}))
        self.assertEqual(self.estoque.quantidade, 2)
        self.assertEqual(self.saldo.quantidade, 6)

    def test_unlinked_earlier_transfer_absorbs_its_own_return(self):
        self.preparar()
        antiga = self.criar_nota_transferida('NF-ANTIGA')
        MovimentacaoEstoque.query.filter_by(nota_fiscal_id=antiga.id).one().nota_fiscal_id = None
        antiga.observacao = '[NF_CANCELADA]'
        db.session.commit()
        self.criar_nota_transferida('NF-NOVA')
        self.enviar()
        self.assertEqual(self.notas_disponiveis(), [])

    def test_partial_return_and_creation_of_missing_client_stock(self):
        self.preparar()
        db.session.delete(self.estoque)
        db.session.commit()
        self.enviar(self.dados(**{'quantidade[]': ['4']}))
        destino = Estoque.query.filter_by(item_id=1, tipo_estoque='cliente', cliente_id=1).one()
        self.assertEqual(destino.quantidade, 4)
        self.assertEqual(destino.valor_unitario, 2)
        self.assertEqual(self.saldo.quantidade, 6)

    def test_client_and_os_are_required_and_must_match(self):
        self.preparar()
        for changes in ({'cliente_id': ''}, {'ordem_servico_id': ''},
                        {'cliente_id': '3'}, {'ordem_servico_id': '3'},
                        {'cliente_id': '2'}, {'tecnico_id': '999'}):
            with self.subTest(changes=changes):
                self.enviar(self.dados(**changes))
                self.conferir_inalterado()

    def test_cannot_consume_company_stock_or_other_customer_os(self):
        self.preparar()
        self.enviar(self.dados(saldo_tecnico_tipo='empresa'))
        self.conferir_inalterado()
        self.enviar(self.dados(**{'quantidade[]': ['11']}))
        self.conferir_inalterado()

    def test_invalid_or_duplicate_items_and_quantities_are_rejected(self):
        self.preparar()
        for changes in (
            {'quantidade[]': ['0']}, {'quantidade[]': ['-1']}, {'quantidade[]': ['1.5']},
            {'codigo[]': ['TESTE01', 'TESTE01'], 'quantidade[]': ['5', '5']},
            {'codigo[]': ['FERR01']}, {'categoria_movimentacao': 'PATRIMONIO'},
            {'origem_tipo': 'empresa'}, {'codigo[]': ['INEXISTENTE']},
            {'condicao_material': 'NOVO_DEF'},
        ):
            with self.subTest(changes=changes):
                self.enviar(self.dados(**changes))
                self.conferir_inalterado()

    def test_entire_batch_is_rejected_when_one_item_has_insufficient_stock(self):
        self.preparar()
        self.enviar(self.dados(**{'codigo[]': ['TESTE01', 'TESTE02'], 'quantidade[]': ['10', '1']}))
        self.conferir_inalterado()

    def test_failed_commit_rolls_back_stock_and_document(self):
        self.preparar()
        with patch.object(db.session, 'commit', side_effect=RuntimeError('test rollback')):
            self.enviar()
        self.conferir_inalterado()

    def test_second_full_return_cannot_duplicate_stock(self):
        self.preparar()
        self.enviar()
        self.enviar()
        self.assertEqual(self.estoque.quantidade, 13)
        self.assertEqual(self.saldo.quantidade, 0)
        self.assertEqual(MovimentacaoEstoque.query.count(), 1)

    def test_documents_identify_customer_destination(self):
        self.preparar()
        self.enviar()
        mov = MovimentacaoEstoque.query.one()
        for path in (f'/movimentacao_estoque/detalhes/{mov.id}', '/movimentacao_estoque/historico'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('Cliente Teste', response.get_data(as_text=True))
        pdf = self.client.get(f'/movimentacao_estoque/detalhes/{mov.id}/pdf')
        self.assertEqual(pdf.status_code, 200)
        self.assertIn('Cliente Teste', pdf.get_data(as_text=True))
        from app.utils.mailer import _build_movimentacao_pdf
        self.assertTrue(_build_movimentacao_pdf(mov).startswith(b'%PDF'))
        excel = self.client.get('/movimentacao_estoque/historico/excel')
        self.assertEqual(excel.status_code, 200)
        sheet = load_workbook(io.BytesIO(excel.data)).active
        self.assertTrue(any('Cliente Teste - OS001' in str(row) for row in sheet.values))

    def test_existing_technician_to_company_return_still_works(self):
        self.preparar()
        self.enviar(self.dados(destino_tipo='empresa', saldo_tecnico_tipo='empresa',
                              cliente_id='', ordem_servico_id=''))
        empresa = Estoque.query.filter_by(item_id=1, tipo_estoque='empresa').one()
        self.assertEqual(empresa.quantidade, 110)
        self.assertEqual(self.saldo.quantidade, 10)
        self.assertEqual(self.estoque.quantidade, 3)


if __name__ == '__main__':
    unittest.main()
