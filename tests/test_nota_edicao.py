import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from test_estoque_minimos import EstoqueMinimosTests
from app.extensions import db
from app.models import (NotaFiscalEntrada, NotaFiscalItem, NotaFiscalEdicao,
                        Estoque, SaldoTecnico, MovimentacaoEstoque,
                        MovimentacaoEstoqueItem, Empresa)
from app.utils.edicao_nota import assinatura


class NotaEdicaoTests(unittest.TestCase):
    setUp = EstoqueMinimosTests.setUp
    tearDown = EstoqueMinimosTests.tearDown

    def preparar(self, cliente=False):
        SaldoTecnico.query.delete()
        self.nota = NotaFiscalEntrada(numero_nf='NF-TESTE', fornecedor='Fornecedor Teste',
                                     tipo_estoque='cliente' if cliente else 'empresa',
                                     cliente_id=1 if cliente else None, tipo_servico_id=1)
        db.session.add(self.nota)
        db.session.flush()
        self.linha = NotaFiscalItem(nota_fiscal_id=self.nota.id, item_id=1,
                                    quantidade=150, valor_unitario=2)
        db.session.add(self.linha)
        if cliente:
            self.saldo = Estoque(item_id=1, tipo_servico_id=1, tipo_estoque='cliente',
                                cliente_id=1, quantidade=150, valor_unitario=2)
            db.session.add(self.saldo)
        else:
            self.saldo = Estoque.query.filter_by(item_id=1).one()
            self.saldo.quantidade = 150
        db.session.commit()
        self.url = f'/nota/{self.nota.id}/editar'

    def dados(self, quantidade=100):
        return {'versao': assinatura(self.nota), 'numero_nf': self.nota.numero_nf,
                'fornecedor': self.nota.fornecedor, 'observacao': 'Conforme nota física',
                'motivo': 'Erro de digitação', f'quantidade_{self.linha.id}': str(quantidade)}

    def test_correct_quantity_both_destinations(self):
        self.preparar()
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, data=self.dados()).status_code, 302)
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 100)
        self.assertEqual(self.linha.quantidade, 100)
        self.assertEqual(self.nota.total_calculado, 200)
        audit = NotaFiscalEdicao.query.one()
        self.assertEqual(audit.antes['itens'][0]['quantidade'], 150)
        self.assertEqual(audit.depois['itens'][0]['quantidade'], 100)

    def test_client_correction_does_not_touch_company_stock(self):
        self.preparar(cliente=True)
        company = Estoque.query.filter_by(item_id=1, tipo_estoque='empresa').one()
        before = company.quantidade
        self.client.post(self.url, data=self.dados())
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 100)
        self.assertEqual(company.quantidade, before)

    def test_movement_blocks_quantity_but_allows_header(self):
        self.preparar()
        mov = MovimentacaoEstoque(origem_tipo='empresa', destino_tipo='tecnico', destino_id=1)
        db.session.add(mov)
        db.session.flush()
        db.session.add(MovimentacaoEstoqueItem(movimentacao_id=mov.id, item_id=1, quantidade=1))
        db.session.commit()
        self.client.post(self.url, data=self.dados())
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 150)
        self.assertEqual(NotaFiscalEdicao.query.count(), 0)
        self.client.post(self.url, data=self.dados(150))
        self.assertEqual(NotaFiscalEdicao.query.count(), 1)

    def test_stale_form_and_invalid_quantity_leave_no_changes(self):
        self.preparar()
        data = self.dados()
        self.nota.observacao = 'Outra pessoa corrigiu'
        db.session.commit()
        self.client.post(self.url, data=data)
        self.assertEqual(NotaFiscalEdicao.query.count(), 0)
        data = self.dados()
        data[f'quantidade_{self.linha.id}'] = '-1'
        self.client.post(self.url, data=data)
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 150)
        self.assertEqual(self.linha.quantidade, 150)

    def test_failure_rolls_back_invoice_stock_and_audit(self):
        self.preparar()
        with patch.object(db.session, 'commit', side_effect=RuntimeError('test rollback')):
            self.client.post(self.url, data=self.dados())
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 150)
        self.assertEqual(self.linha.quantidade, 150)
        self.assertEqual(NotaFiscalEdicao.query.count(), 0)

    def test_destination_and_price_cannot_be_changed_by_post(self):
        self.preparar()
        data = self.dados()
        data.update(cliente_id='2', tipo_estoque='cliente', valor_unitario='999')
        self.client.post(self.url, data=data)
        db.session.expire_all()
        self.assertEqual(self.nota.tipo_estoque, 'empresa')
        self.assertIsNone(self.nota.cliente_id)
        self.assertEqual(self.linha.valor_unitario, 2)

    def test_increase_and_duplicate_number(self):
        self.preparar()
        self.client.post(self.url, data=self.dados(175))
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 175)
        db.session.add(NotaFiscalEntrada(numero_nf='OUTRA', fornecedor='Fornecedor Teste', tipo_estoque='empresa'))
        db.session.commit()
        data = self.dados(100)
        data['numero_nf'] = 'OUTRA'
        self.client.post(self.url, data=data)
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 175)
        self.assertEqual(self.nota.numero_nf, 'NF-TESTE')

    def test_insufficient_stock_rolls_back_all_lines(self):
        self.preparar()
        second = NotaFiscalItem(nota_fiscal_id=self.nota.id, item_id=2, quantidade=150, valor_unitario=3)
        db.session.add(second)
        db.session.commit()
        data = self.dados()
        data[f'quantidade_{second.id}'] = '1'
        self.client.post(self.url, data=data)
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 150)
        self.assertEqual(self.linha.quantidade, 150)
        self.assertEqual(second.quantidade, 150)
        self.assertEqual(NotaFiscalEdicao.query.count(), 0)

    def test_cancelled_note_cannot_be_edited(self):
        self.preparar()
        self.nota.observacao = '[NF_CANCELADA]'
        db.session.commit()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.post(self.url, data=self.dados())
        self.assertEqual(NotaFiscalEdicao.query.count(), 0)

    def preparar_troca(self):
        self.preparar(cliente=True)
        db.session.add(Empresa(id=3, razao_social='Jaco', cnpj='12345678901236', tipo_empresa='cliente'))
        self.saldo.quantidade = 180  # 150 da nota e 30 de outra entrada.
        self.destino = Estoque(item_id=1, tipo_servico_id=1, tipo_estoque='cliente',
                               cliente_id=3, quantidade=10, valor_unitario=7)
        db.session.add(self.destino)
        db.session.commit()

    def dados_troca(self, quantidade=150):
        data = self.dados(quantidade)
        data.update(novo_cliente_id='3', confirmar_destino='1')
        return data

    def test_change_client_moves_only_invoice_quantity_and_keeps_existing_stock(self):
        self.preparar_troca()
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, data=self.dados_troca())
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 30)
        self.assertEqual(self.destino.quantidade, 160)
        self.assertEqual(self.destino.valor_unitario, 7)
        self.assertEqual(self.nota.cliente_id, 3)
        self.assertEqual(self.linha.quantidade, 150)
        audit = NotaFiscalEdicao.query.one()
        self.assertEqual(audit.antes['cliente_id'], 1)
        self.assertEqual(audit.depois['cliente_id'], 3)
        self.assertEqual(audit.depois['cliente_nome'], 'Jaco')

    def test_change_client_rejects_larger_and_smaller_quantities_even_with_extra_stock(self):
        self.preparar_troca()
        for quantidade in (180, 100):
            with self.subTest(quantidade=quantidade):
                self.client.post(self.url, data=self.dados_troca(quantidade))
                db.session.expire_all()
                self.assertEqual(self.saldo.quantidade, 180)
                self.assertEqual(self.destino.quantidade, 10)
                self.assertEqual(self.nota.cliente_id, 1)
                self.assertEqual(self.linha.quantidade, 150)
                self.assertEqual(NotaFiscalEdicao.query.count(), 0)

    def test_change_client_requires_confirmation_and_valid_client(self):
        self.preparar_troca()
        for updates in ({'confirmar_destino': ''}, {'novo_cliente_id': '2'}, {'novo_cliente_id': '999'}):
            data = self.dados_troca()
            data.update(updates)
            self.client.post(self.url, data=data)
            db.session.expire_all()
            self.assertEqual(self.saldo.quantidade, 180)
            self.assertEqual(self.destino.quantidade, 10)
            self.assertEqual(self.nota.cliente_id, 1)
            self.assertEqual(NotaFiscalEdicao.query.count(), 0)

    def test_change_client_blocks_moved_material(self):
        self.preparar_troca()
        mov = MovimentacaoEstoque(origem_tipo='cliente', origem_id=1,
                                  destino_tipo='tecnico', destino_id=1)
        mov.itens.append(MovimentacaoEstoqueItem(item_id=1, quantidade=1))
        db.session.add(mov)
        db.session.commit()
        self.client.post(self.url, data=self.dados_troca())
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 180)
        self.assertEqual(self.destino.quantidade, 10)
        self.assertEqual(self.nota.cliente_id, 1)

    def test_change_client_rolls_back_all_items_when_one_has_insufficient_stock(self):
        self.preparar_troca()
        second = NotaFiscalItem(nota_fiscal_id=self.nota.id, item_id=2, quantidade=20, valor_unitario=3)
        db.session.add(second)
        db.session.add(Estoque(item_id=2, tipo_servico_id=1, tipo_estoque='cliente',
                               cliente_id=1, quantidade=19))
        db.session.commit()
        data = self.dados_troca()
        data[f'quantidade_{second.id}'] = '20'
        self.client.post(self.url, data=data)
        db.session.expire_all()
        self.assertEqual(self.saldo.quantidade, 180)
        self.assertEqual(self.destino.quantidade, 10)
        self.assertEqual(self.nota.cliente_id, 1)
        self.assertEqual(NotaFiscalEdicao.query.count(), 0)

    def test_change_client_creates_destination_and_can_be_reversed(self):
        self.preparar_troca()
        db.session.delete(self.destino)
        db.session.commit()
        self.client.post(self.url, data=self.dados_troca())
        db.session.expire_all()
        novo = Estoque.query.filter_by(item_id=1, tipo_estoque='cliente', cliente_id=3).one()
        self.assertEqual(novo.quantidade, 150)
        self.assertEqual(self.saldo.quantidade, 30)
        data = self.dados_troca()
        data['novo_cliente_id'] = '1'
        self.client.post(self.url, data=data)
        db.session.expire_all()
        self.assertEqual(self.nota.cliente_id, 1)
        self.assertEqual(novo.quantidade, 0)
        self.assertEqual(self.saldo.quantidade, 180)


if __name__ == '__main__':
    unittest.main()
