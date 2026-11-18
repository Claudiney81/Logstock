import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
from test_estoque_minimos import EstoqueMinimosTests
from app.extensions import db
from app.models import SaldoTecnico, MovimentacaoEstoque, Estoque, Tecnico
from unittest.mock import patch


class TransferenciaTecnicosTests(unittest.TestCase):
    setUp = EstoqueMinimosTests.setUp
    tearDown = EstoqueMinimosTests.tearDown

    def enviar(self, linhas=None, **extras):
        self.client.get('/movimentacao_estoque/entre-tecnicos?origem_id=1')
        with self.client.session_transaction() as s:
            token=s['transferencia_tecnicos_csrf']
        saldo=SaldoTecnico.query.filter_by(tecnico_id=1,item_id=1,tipo_estoque='empresa').one()
        data={'csrf_token':token,'origem_id':'1','destino_id':'2',
              f'quantidade_{saldo.id}':'7','observacao':'Teste'}
        if linhas is not None:
            data={k:v for k,v in data.items() if not k.startswith('quantidade_')}
            data.update(linhas)
        data.update(extras)
        r=self.client.post('/movimentacao_estoque/entre-tecnicos',data=data)
        db.session.expire_all()
        return r,data

    def test_transfere_empresa_sem_alterar_estoque_e_bloqueia_reenvio(self):
        estoque=[(s.id,s.quantidade) for s in Estoque.query.all()]
        r,data=self.enviar()
        self.assertEqual(r.status_code,302)
        self.assertEqual(SaldoTecnico.query.filter_by(tecnico_id=1,item_id=1).one().quantidade,43)
        destino=SaldoTecnico.query.filter_by(tecnico_id=2,item_id=1).one()
        self.assertEqual(destino.quantidade,7)
        self.assertEqual(destino.valor_unitario,12.5)
        self.assertEqual(estoque,[(s.id,s.quantidade) for s in Estoque.query.all()])
        mov=MovimentacaoEstoque.query.one()
        self.assertEqual((mov.origem_id,mov.destino_id),(1,2))
        self.assertEqual(mov.itens[0].quantidade,7)
        self.assertEqual(self.client.post('/movimentacao_estoque/entre-tecnicos',data=data).status_code,400)
        self.assertEqual(self.client.get(r.location).status_code,200)
        historico=self.client.get('/movimentacao_estoque/historico')
        self.assertEqual(historico.status_code,200)
        self.assertIn('Tecnico Teste &rarr; Outro Tecnico',historico.get_data(as_text=True))
        pdf=self.client.get(f'/movimentacao_estoque/detalhes/{mov.id}/pdf')
        self.assertEqual(pdf.status_code,200)
        self.assertIn('Tecnico Teste',pdf.get_data(as_text=True))
        self.assertIn('Outro Tecnico',pdf.get_data(as_text=True))

    def test_preserva_cliente_os_obra_valor_e_outros_saldos(self):
        saldo=SaldoTecnico(tecnico_id=1,item_id=1,tipo_servico_id=1,tipo_estoque='cliente',
            cliente_id=1,ordem_servico_id=1,quantidade=10,valor_unitario=3.75,
            endereco='Rua da obra',bairro='Centro',codigo_imovel='IM-1')
        db.session.add(saldo);db.session.commit()
        r,_=self.enviar({f'quantidade_{saldo.id}':'4'})
        self.assertEqual(r.status_code,302)
        destino=SaldoTecnico.query.filter_by(tecnico_id=2,tipo_estoque='cliente').one()
        self.assertEqual((destino.cliente_id,destino.ordem_servico_id,destino.tipo_servico_id),(1,1,1))
        self.assertEqual((destino.endereco,destino.bairro,destino.codigo_imovel,destino.valor_unitario),('Rua da obra','Centro','IM-1',3.75))
        self.assertEqual(saldo.quantidade,6)
        self.assertEqual(SaldoTecnico.query.filter_by(tecnico_id=1,item_id=1,tipo_estoque='empresa').one().quantidade,50)

    def test_sem_saldo_ou_quantidade_invalida_nao_transfere_nada(self):
        saldos=SaldoTecnico.query.filter_by(tecnico_id=1).all()
        for valor in ['51','-1','1.5','abc']:
            self.enviar({f'quantidade_{saldos[0].id}':'2',f'quantidade_{saldos[1].id}':valor})
            self.assertEqual(MovimentacaoEstoque.query.count(),0)
            self.assertTrue(all(s.quantidade==50 for s in saldos))

    def test_mesmo_tecnico_inativo_e_saldo_de_outro_bloqueados(self):
        self.enviar(destino_id='1')
        self.assertEqual(MovimentacaoEstoque.query.count(),0)
        t=db.session.get(Tecnico,2);t.status='Inativo';db.session.commit()
        self.enviar();self.assertEqual(MovimentacaoEstoque.query.count(),0)
        t.status='Ativo';db.session.commit()
        self.enviar({'quantidade_999999':'1'})
        self.assertEqual(MovimentacaoEstoque.query.count(),0)

    def test_acumula_destino_e_multiplos_itens(self):
        self.enviar()
        saldos=SaldoTecnico.query.filter_by(tecnico_id=1).all()
        self.enviar({f'quantidade_{s.id}':'3' for s in saldos})
        self.assertEqual(SaldoTecnico.query.filter_by(tecnico_id=2,item_id=1).one().quantidade,10)
        self.assertEqual(SaldoTecnico.query.filter_by(tecnico_id=2,item_id=2).one().quantidade,3)

    def test_rollback_em_falha_durante_gravacao(self):
        self.client.get('/movimentacao_estoque/entre-tecnicos?origem_id=1')
        from sqlalchemy.exc import SQLAlchemyError
        with patch('app.routes.transferencia_tecnicos.db.session.commit',side_effect=SQLAlchemyError('teste')):
            self.enviar()
        self.assertEqual(MovimentacaoEstoque.query.count(),0)
        self.assertEqual(SaldoTecnico.query.filter_by(tecnico_id=2).count(),0)
        self.assertTrue(all(s.quantidade==50 for s in SaldoTecnico.query.filter_by(tecnico_id=1)))

    def test_empresa_e_cliente_na_mesma_operacao_permanecem_separados(self):
        cliente=SaldoTecnico(tecnico_id=1,item_id=1,tipo_servico_id=1,tipo_estoque='cliente',
            cliente_id=1,ordem_servico_id=1,quantidade=8,valor_unitario=2)
        db.session.add(cliente);db.session.commit()
        empresa=SaldoTecnico.query.filter_by(tecnico_id=1,item_id=1,tipo_estoque='empresa').one()
        self.enviar({f'quantidade_{cliente.id}':'2',f'quantidade_{empresa.id}':'3'})
        self.assertEqual(MovimentacaoEstoque.query.count(),2)
        self.assertEqual(SaldoTecnico.query.filter_by(tecnico_id=2,item_id=1,tipo_estoque='empresa').one().quantidade,3)
        self.assertEqual(SaldoTecnico.query.filter_by(tecnico_id=2,item_id=1,tipo_estoque='cliente').one().quantidade,2)

    def test_permissoes_csrf_e_patrimonio(self):
        self.assertEqual(self.client.post('/movimentacao_estoque/entre-tecnicos',data={}).status_code,400)
        db.session.add(SaldoTecnico(tecnico_id=1,item_id=3,tipo_servico_id=1,tipo_estoque='empresa',quantidade=1))
        db.session.commit()
        patrimonio=SaldoTecnico.query.filter_by(item_id=3).one()
        self.enviar({f'quantidade_{patrimonio.id}':'1'})
        self.assertEqual(MovimentacaoEstoque.query.count(),0)
        with self.client.session_transaction() as session:
            session.clear()
            session['_user_id'] = '2'
            session['_fresh'] = True
        from flask import g
        g.pop('_login_user', None)
        self.assertIn(self.client.get('/movimentacao_estoque/entre-tecnicos').status_code, (302, 403))



if __name__=='__main__': unittest.main()
