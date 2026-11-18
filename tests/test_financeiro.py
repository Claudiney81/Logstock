import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.extensions import db
from app.models import Usuario
from app.financeiro_models import CadastroFinanceiro, ClienteFinanceiro, ContratoFinanceiro, ParcelaFinanceira, RecebimentoFinanceiro, EventoFinanceiro
from app.financeiro_service import gerar_parcelas, situacao, dinheiro, vencimento_mensal
from app.utils.datas import hoje_local


class FinanceiroTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {'LOGISTOCK_ADMIN_EMAIL': '', 'LOGISTOCK_ADMIN_PASSWORD': ''}):
            self.app = create_app({'TESTING': True, 'SECRET_KEY': 'financeiro-tests',
                'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(Path(self.temp.name, 'test.db')).replace('\\','/'),
                'FINANCEIRO_HABILITADO': True, 'MAIL_SUPPRESS_SEND': True})
        self.ctx = self.app.app_context(); self.ctx.push()
        for i,perfil in enumerate(['admin','financeiro','estoque','gerente'],1):
            db.session.add(Usuario(id=i,nome=perfil,email=perfil+'@teste.local',senha_hash='unused',perfil=perfil))
        db.session.commit()
        self.client = self.app.test_client()
        self.login(1)

    def tearDown(self):
        db.session.remove();db.engine.dispose();self.ctx.pop();self.temp.cleanup()

    def login(self, uid):
        from flask import g
        g.pop('_login_user', None)
        with self.client.session_transaction() as s:
            s.clear();s['_user_id']=str(uid);s['_fresh']=True;s['financeiro_csrf']='test-token'

    def post(self,path,**data):
        return self.client.post(path,data={'csrf_token':'test-token',**data})

    def contrato(self, modalidade='comodato_variavel', codigo='TESTE'):
        c=ContratoFinanceiro(codigo=codigo,cliente='Bucar Engenharia',modalidade=modalidade,
            quantidade_parcelas=48,primeiro_vencimento=date(2024,1,31),base_mensal=Decimal('1800.00'),criado_por=1)
        gerar_parcelas(c);db.session.add(c);db.session.commit();return c

    def test_previsao_transicao_fixed_and_month_end(self):
        c=self.contrato()
        self.assertEqual(c.parcelas[35].previsao,Decimal('1260'))
        self.assertEqual(c.parcelas[36].previsao,Decimal('900'))
        self.assertEqual(c.parcelas[37].previsao,Decimal('900'))
        self.assertIsNone(c.parcelas[36].valor_real)
        self.assertEqual(c.parcelas[1].vencimento,date(2024,2,29))
        self.assertEqual(c.parcelas[2].vencimento,date(2024,3,31))
        fixo=self.contrato('comodato_fixo','FIXO')
        self.assertEqual(fixo.parcelas[36].valor_real,Decimal('1800'))
        self.assertEqual(vencimento_mensal(date(2026,12,10),1),date(2027,1,10))

    def test_busca_sem_acentos(self):
        cliente=ClienteFinanceiro(nome='João Conceição',ativo=True,criado_por=1)
        db.session.add(cliente);db.session.flush()
        c=self.contrato()
        c.cliente_id=cliente.id
        db.session.commit()
        for termo in ['joao', 'JOAO', 'João', 'conceicao']:
            for rota in ['/financeiro/clientes', '/financeiro/contratos', '/financeiro/consultas']:
                resposta=self.client.get(rota,query_string={'busca':termo})
                self.assertEqual(resposta.status_code,200)
                self.assertIn('João Conceição',resposta.get_data(as_text=True))
        resposta=self.client.get('/financeiro/clientes',query_string={'busca':'inexistente'})
        self.assertNotIn('João Conceição',resposta.get_data(as_text=True))

    def test_comodato_181_parcelas_aguardam_leitura(self):
        c=ContratoFinanceiro(codigo='BELA-TESTE',cliente='Cliente Exemplo',
            modalidade='comodato_variavel',quantidade_parcelas=181,
            primeiro_vencimento=date(2025,4,10),base_mensal=Decimal('2737.00'),criado_por=1)
        gerar_parcelas(c)
        self.assertEqual(len(c.parcelas),181)
        self.assertTrue(all(p.previsao==Decimal('1915.90') for p in c.parcelas[:36]))
        self.assertTrue(all(p.previsao==Decimal('1368.50') for p in c.parcelas[36:]))
        self.assertEqual(c.parcelas[36].vencimento,date(2028,4,10))
        self.assertEqual(c.parcelas[37].vencimento,date(2028,5,10))
        self.assertTrue(all(p.valor_real is None and not p.recebimentos for p in c.parcelas))

    def test_apuracao_recebimento_integral_and_audit(self):
        p=self.contrato().parcelas[0];pid=p.id
        self.post(f'/financeiro/parcelas/{pid}/receber',versao=p.versao,valor='655,31',data_pagamento='2024-01-10')
        self.assertEqual(RecebimentoFinanceiro.query.count(),0)
        self.post(f'/financeiro/parcelas/{pid}/apurar',versao=p.versao,valor_real='655,31',nota_kit='1278')
        self.assertEqual(p.valor_real,Decimal('655.31'));self.assertEqual(p.previsao,Decimal('1260'))
        for valor in ('600','700'):
            self.post(f'/financeiro/parcelas/{pid}/receber',versao=p.versao,valor=valor,data_pagamento='2024-01-10')
        self.assertEqual(RecebimentoFinanceiro.query.count(),0)
        self.post(f'/financeiro/parcelas/{pid}/receber',versao=p.versao,valor='655,31',data_pagamento='2024-01-10')
        self.assertEqual(RecebimentoFinanceiro.query.count(),1);self.assertEqual(situacao(p),'Pago')
        self.post(f'/financeiro/parcelas/{pid}/receber',versao=p.versao,valor='655,31',data_pagamento='2024-01-10')
        self.post(f'/financeiro/parcelas/{pid}/apurar',versao=p.versao,valor_real='10',observacao='alteração')
        self.assertEqual(RecebimentoFinanceiro.query.count(),1);self.assertEqual(p.valor_real,Decimal('655.31'))
        self.assertEqual(EventoFinanceiro.query.count(),2)

    def test_apuracao_igual_nao_duplica_historico(self):
        p=self.contrato().parcelas[0]
        self.post(f'/financeiro/parcelas/{p.id}/apurar',versao=p.versao,valor_real='1181',nota_kit='1528')
        versao=p.versao
        for motivo in ['', 'ND']:
            self.post(f'/financeiro/parcelas/{p.id}/apurar',versao=p.versao,
                valor_real='1181',nota_kit='1528',observacao=motivo)
        self.assertEqual(EventoFinanceiro.query.count(),1)
        self.assertEqual(p.versao,versao)
        self.assertEqual(p.observacao,'')

    def test_avisos_vencimento_nas_telas(self):
        p=self.contrato().parcelas[0]
        p.valor_real=Decimal('100')
        rotas=[f'/financeiro/contratos/{p.contrato_id}', '/financeiro/consultas',
               '/financeiro/lancamentos', f'/financeiro/parcelas/{p.id}/lancamento']
        for dias,texto,classe in [(5,'Vence em 5 dias','fin-upcoming'),
                                  (1,'Vence em 1 dia','fin-upcoming'),
                                  (0,'Vence hoje','fin-today'),
                                  (-3,'Atrasada há 3 dias','fin-overdue')]:
            p.vencimento=hoje_local()+timedelta(days=dias);db.session.commit()
            for rota in rotas:
                resposta=self.client.get(rota)
                self.assertEqual(resposta.status_code,200)
                self.assertIn(texto,resposta.get_data(as_text=True))
                self.assertIn(classe,resposta.get_data(as_text=True))
        p.valor_real=None;db.session.commit()
        html=self.client.get(rotas[-1]).get_data(as_text=True)
        self.assertIn('Aguardando apuração',html)
        self.assertIn('Vencimento há 3 dias',html)
        self.post(f'/financeiro/parcelas/{p.id}/apurar',versao=p.versao,valor_real='100')
        self.post(f'/financeiro/parcelas/{p.id}/receber',versao=p.versao,valor='100',data_pagamento=hoje_local().isoformat())
        html=self.client.get(rotas[-1]).get_data(as_text=True)
        self.assertIn('fin-paid',html)
        self.assertNotIn('Atrasada há',html)

    def test_status_zero_today_and_pending(self):
        p=self.contrato().parcelas[0];p.vencimento=hoje_local()
        self.assertEqual(situacao(p),'Aguardando apuração')
        p.valor_real=Decimal('0');self.assertEqual(situacao(p),'Vence hoje')
        p.vencimento-=timedelta(days=1);self.assertEqual(situacao(p),'Atrasado')
        db.session.commit()
        self.post(f'/financeiro/parcelas/{p.id}/receber',versao=p.versao,valor='0',data_pagamento=hoje_local().isoformat())
        self.assertEqual(situacao(p),'Pago')

    def test_access_csrf_and_feature_flag(self):
        c=self.contrato()
        self.login(2)
        for path in ['/financeiro/','/financeiro/contratos/novo',f'/financeiro/contratos/{c.id}','/financeiro/relatorios','/financeiro/relatorios/exportar']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertEqual(self.client.get('/estoque/saldo').status_code,403)
        self.assertEqual(self.client.get('/').location,'/financeiro/')
        html=self.client.get('/financeiro/').get_data(as_text=True)
        self.assertIn('Gestão de Estoque',html)
        self.assertEqual(html.count('aria-disabled="true"'),9)
        self.assertNotIn('href="/estoque/saldo"',html)
        self.assertEqual(self.client.post('/financeiro/contratos/novo',data={}).status_code,400)
        self.login(3);self.assertEqual(self.client.get('/financeiro/').status_code,403)
        self.assertEqual(self.client.get('/financeiro/relatorios/exportar').status_code,403)
        self.login(4);self.assertEqual(self.client.get('/financeiro/').status_code,200)
        self.app.config['FINANCEIRO_HABILITADO']=False
        self.assertEqual(self.client.get('/financeiro/').status_code,404)

    def test_filters_receipt_date_csv_and_pages(self):
        c=self.contrato('venda');p=c.parcelas[0]
        self.post(f'/financeiro/parcelas/{p.id}/receber',versao=p.versao,valor='1800',data_pagamento='2025-02-05')
        for path in ['/financeiro/','/financeiro/contratos/novo',f'/financeiro/contratos/{c.id}','/financeiro/relatorios']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        base='/financeiro/relatorios/exportar?'
        text=self.client.get(base+'tipo=recebimentos&inicio=2025-02-01&fim=2025-02-28').data.decode('utf-8-sig')
        self.assertIn('1800,00',text);self.assertIn('05/02/2025',text)
        text=self.client.get(base+'tipo=cobrancas&inicio=2025-02-01&fim=2025-02-28').data.decode('utf-8-sig')
        self.assertNotIn('05/02/2025',text)
        text=self.client.get(base+'tipo=recebimentos&inicio=2026-01-01').data.decode('utf-8-sig')
        self.assertNotIn('Bucar Engenharia',text)
        self.assertEqual(self.client.get(base+'inicio=2026-12-01&fim=2026-01-01').status_code,400)

    def test_create_optional_total_duplicate_and_invalid_money(self):
        self.post('/financeiro/clientes/novo',nome='Cliente',ativo='1')
        cliente=ClienteFinanceiro.query.one()
        data=dict(codigo='NOVO',cliente_id=str(cliente.id),modalidade='venda',quantidade_parcelas='3',
                  primeiro_vencimento='2026-12-31',base_mensal='1.000,00',valor_total='3.000,00')
        self.assertEqual(self.post('/financeiro/contratos/novo',**data).status_code,302)
        c=ContratoFinanceiro.query.one();self.assertEqual(c.valor_total,Decimal('3000'))
        self.assertEqual(len(c.parcelas),3)
        self.post('/financeiro/contratos/novo',**data)
        self.assertEqual(ContratoFinanceiro.query.count(),1)
        for valor in ['NaN','Infinity','-1','1.234','1000000000000']:
            with self.assertRaises(ValueError):dinheiro(valor)
        self.assertEqual(dinheiro('0'),Decimal('0'))

    def test_stale_edit_and_future_payment(self):
        p=self.contrato('venda').parcelas[0]
        self.post(f'/financeiro/parcelas/{p.id}/apurar',versao=0,valor_real='1',observacao='teste')
        self.assertEqual(p.valor_real,Decimal('1800'))
        self.post(f'/financeiro/parcelas/{p.id}/receber',versao=p.versao,valor='1800',data_pagamento=(hoje_local()+timedelta(days=1)).isoformat())
        self.assertEqual(RecebimentoFinanceiro.query.count(),0)

    def test_client_registration_contract_and_receivables_flow(self):
        self.login(2)
        self.post('/financeiro/clientes/novo',nome='Cliente Financeiro',documento='123.456.789-01',
            telefone='11999990000',email='cliente@example.com',ativo='1')
        cadastro=ClienteFinanceiro.query.one()
        self.assertEqual(cadastro.documento,'12345678901')
        self.assertEqual(cadastro.criado_por,2)
        data=dict(codigo='CAD-001',cliente_id=str(cadastro.id),modalidade='venda',quantidade_parcelas='2',
            primeiro_vencimento='2026-01-10',base_mensal='100',valor_total='200')
        self.post('/financeiro/contratos/novo',**data)
        c=ContratoFinanceiro.query.one()
        self.assertEqual(c.cliente_id,cadastro.id)
        self.assertEqual(c.criado_por,2)
        p=c.parcelas[0]
        self.post(f'/financeiro/parcelas/{p.id}/receber',versao=p.versao,valor='100',data_pagamento='2026-01-10',destino='lancamento')
        base=f'/financeiro/relatorios/exportar?tipo=a_receber&cliente_id={cadastro.id}'
        text=self.client.get(base).data.decode('utf-8-sig')
        self.assertEqual(len(text.strip().splitlines()),2)
        self.assertIn('10/02/2026',text)
        self.assertNotIn('10/01/2026',text)
        other=ClienteFinanceiro(nome='Outro cliente',ativo=True,criado_por=2)
        db.session.add(other);db.session.commit()
        text=self.client.get(f'/financeiro/relatorios/exportar?cliente_id={other.id}').data.decode('utf-8-sig')
        self.assertEqual(len(text.strip().splitlines()),1)
        for path in ['/financeiro/clientes','/financeiro/clientes/novo',f'/financeiro/clientes/{cadastro.id}',
            f'/financeiro/clientes/{cadastro.id}/editar',f'/financeiro/lancamentos?cliente_id={cadastro.id}',
            f'/financeiro/parcelas/{p.id}/lancamento','/financeiro/relatorios?tipo=a_receber']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200,path)
            self.assertIn('Usuário logado',response.get_data(as_text=True))
        html=self.client.get(f'/financeiro/parcelas/{p.id}/lancamento').get_data(as_text=True)
        self.assertIn('Registrado por',html)
        self.assertIn('financeiro',html)

    def test_client_edit_inactivate_duplicate_document_and_permissions(self):
        self.post('/financeiro/clientes/novo',nome='Cliente Um',documento='12345678901',ativo='1')
        cadastro=ClienteFinanceiro.query.one()
        self.post('/financeiro/clientes/novo',nome='Cliente Dois',documento='12345678901',ativo='1')
        self.assertEqual(ClienteFinanceiro.query.count(),1)
        self.post(f'/financeiro/clientes/{cadastro.id}/editar',nome='Cliente Alterado',documento='12345678901')
        self.assertEqual(cadastro.nome,'Cliente Alterado')
        self.assertFalse(cadastro.ativo)
        self.post('/financeiro/contratos/novo',codigo='INATIVO',cliente_id=str(cadastro.id),modalidade='venda',
            quantidade_parcelas='2',primeiro_vencimento='2026-01-10',base_mensal='100')
        self.assertEqual(ContratoFinanceiro.query.count(),0)
        self.login(3)
        self.assertEqual(self.client.get('/financeiro/clientes').status_code,403)
        self.assertEqual(self.post('/financeiro/clientes/novo',nome='Proibido',ativo='1').status_code,403)
        self.assertEqual(ClienteFinanceiro.query.count(),1)
        self.login(2)
        self.app.config['FINANCEIRO_PERMISSOES']={'financeiro':{'consultar','relatorios'}}
        self.assertEqual(self.client.get('/financeiro/clientes').status_code,200)
        self.assertEqual(self.client.get('/financeiro/clientes/novo').status_code,403)

    def test_receivables_exclude_unapplied_estimates(self):
        c=self.contrato()
        p=c.parcelas[0]
        self.post(f'/financeiro/parcelas/{p.id}/apurar',versao=p.versao,valor_real='655,31',destino='lancamento')
        text=self.client.get('/financeiro/relatorios/exportar?tipo=a_receber').data.decode('utf-8-sig')
        self.assertEqual(len(text.strip().splitlines()),2)
        self.assertIn('655,31',text)
        self.assertNotIn('Aguardando apuração',text)

    def test_continue_from_new_client_with_spreadsheet_fields(self):
        response=self.post('/financeiro/clientes/novo',nome='Novo cliente mensal',ativo='1',proximo='contrato')
        cadastro=ClienteFinanceiro.query.one()
        self.assertIn(f'/financeiro/contratos/novo?cliente_id={cadastro.id}',response.location)
        data=dict(cliente_id=str(cadastro.id),modalidade='manutencao_sfv',quantidade_parcelas='3',
            primeiro_vencimento='2026-12-10',base_mensal='250,50',fornecedor='Fornecedor novo',
            forma_pagamento='Parcelado',nota_kit='NF-123',observacao='Serviço mensal')
        response=self.post('/financeiro/contratos/novo',**data)
        self.assertEqual(response.status_code,302)
        c=ContratoFinanceiro.query.one()
        self.assertTrue(c.codigo.startswith('CTR-'))
        self.assertEqual(c.fornecedor,'Fornecedor novo')
        self.assertEqual(c.forma_pagamento,'Parcelado')
        self.assertEqual(c.parcelas[0].nota_kit,'NF-123')
        self.assertEqual(c.parcelas[0].valor_real,Decimal('250.50'))
        html=self.client.get('/financeiro/contratos/novo').get_data(as_text=True)
        self.assertIn('Fornecedor novo',html)
        self.assertIn('Manutenção João',html)
        self.assertIn('Manutenção SFV',html)
        self.assertIn('Nº NF',html)

    def test_change_installment_data_preserves_values_and_audits(self):
        c=self.contrato()
        p=c.parcelas[0]
        original=c.parcelas[1].vencimento
        data=dict(versao=p.versao,vencimento='2026-12-15',nota_kit='NF-999',
            observacao='Leitura pendente',motivo='Ajuste acordado com cliente')
        response=self.post(f'/financeiro/parcelas/{p.id}/dados',**data)
        self.assertIn('/lancamento',response.location)
        self.assertEqual(p.vencimento,date(2026,12,15))
        self.assertEqual(p.nota_kit,'NF-999')
        self.assertEqual(p.previsao,Decimal('1260'))
        self.assertIsNone(p.valor_real)
        self.assertEqual(c.parcelas[1].vencimento,original)
        self.assertEqual(EventoFinanceiro.query.one().acao,'dados_parcela')
        self.post(f'/financeiro/parcelas/{p.id}/dados',**{**data,'vencimento':'2027-01-01'})
        self.assertEqual(p.vencimento,date(2026,12,15))
        self.assertEqual(EventoFinanceiro.query.count(),1)
        self.post(f'/financeiro/parcelas/{p.id}/apurar',versao=p.versao,valor_real='100')
        self.post(f'/financeiro/parcelas/{p.id}/receber',versao=p.versao,valor='100',data_pagamento=hoje_local().isoformat())
        self.post(f'/financeiro/parcelas/{p.id}/dados',**{**data,'versao':p.versao,'vencimento':'2027-01-01'})
        self.assertEqual(p.vencimento,date(2026,12,15))

    def test_reports_unify_exports(self):
        self.login(2)
        response = self.client.get('/financeiro/exportacoes')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/financeiro/relatorios'))
        html = self.client.get('/financeiro/relatorios?tipo=cobrancas&situacao=Pago').get_data(as_text=True)
        self.assertIn('Baixar Excel', html)
        self.assertIn('Baixar CSV', html)
        self.assertIn('formato=xlsx', html)
        self.assertIn('situacao=Pago', html)
        self.assertIn('name="conjunto"', html)
        self.assertNotIn('href="/financeiro/exportacoes"', html)

    def test_organized_sections_and_auxiliary_registrations(self):
        self.login(2)
        for path in ['/financeiro/','/financeiro/cadastros','/financeiro/contratos','/financeiro/registros/novo',
            '/financeiro/consultas','/financeiro/relatorios','/financeiro/cadastros/fornecedores',
            '/financeiro/cadastros/formas_pagamento']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.post('/financeiro/cadastros/fornecedores',nome='Fornecedor Equipe')
        item=CadastroFinanceiro.query.one()
        self.assertEqual(item.criado_por,2)
        html=self.client.get('/financeiro/contratos/novo').get_data(as_text=True)
        self.assertIn('value="Fornecedor Equipe"',html)
        self.post('/financeiro/cadastros/fornecedores',nome='fornecedor equipe')
        self.assertEqual(CadastroFinanceiro.query.count(),1)
        self.post(f'/financeiro/cadastros/fornecedores/{item.id}/editar')
        self.assertFalse(item.ativo)
        html=self.client.get('/financeiro/contratos/novo').get_data(as_text=True)
        self.assertNotIn('value="Fornecedor Equipe"',html)
        self.assertEqual(self.client.get('/financeiro/cadastros/inexistente').status_code,404)
        self.login(3)
        self.assertEqual(self.client.get('/financeiro/exportacoes').status_code,403)
        self.assertEqual(self.post('/financeiro/cadastros/fornecedores',nome='Proibido').status_code,403)

    def test_queries_by_note_and_registration_responsible(self):
        c=self.contrato('venda','VENDA-UM')
        c.parcelas[0].nota_kit='NOTA-BUSCA'
        outro=self.contrato('manutencao_sfv','SERVICO-DOIS')
        outro.criado_por=2
        db.session.commit()
        text=self.client.get('/financeiro/relatorios/exportar?busca=NOTA-BUSCA').data.decode('utf-8-sig')
        self.assertEqual(len(text.strip().splitlines()),2)
        self.assertIn('VENDA-UM',text)
        self.assertNotIn('SERVICO-DOIS',text)
        text=self.client.get('/financeiro/relatorios/exportar?responsavel_id=2').data.decode('utf-8-sig')
        self.assertIn('SERVICO-DOIS',text)
        self.assertNotIn('VENDA-UM',text)
        self.assertEqual(self.client.get('/financeiro/relatorios/exportar?responsavel_id=abc').status_code,400)
        html=self.client.get('/financeiro/consultas?busca=NOTA-BUSCA').get_data(as_text=True)
        self.assertIn('NOTA-BUSCA',html)

    def test_excel_exports_have_numeric_values_and_safe_text(self):
        import io
        from openpyxl import load_workbook
        self.post('/financeiro/clientes/novo',nome='=Nome de teste',ativo='1')
        cadastro=ClienteFinanceiro.query.one()
        self.post('/financeiro/contratos/novo',codigo='XLSX',cliente_id=str(cadastro.id),modalidade='venda',
            quantidade_parcelas='2',primeiro_vencimento='2026-01-10',base_mensal='250,50')
        for path in ['/financeiro/exportacoes/cadastros?conjunto=clientes&formato=xlsx',
            '/financeiro/exportacoes/cadastros?conjunto=contratos&formato=xlsx',
            '/financeiro/relatorios/exportar?formato=xlsx']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200,path)
            book=load_workbook(io.BytesIO(response.data));sheet=book.active
            self.assertEqual(sheet.max_row,2 if 'clientes&' in path or 'contratos&' in path else 3)
            self.assertEqual(sheet.freeze_panes,'A2')
            for row in sheet:
                for cell in row:
                    self.assertNotEqual(cell.data_type,'f')
            if 'relatorios/' in path:
                self.assertEqual(sheet['G2'].value,250.5)
                self.assertEqual(sheet['G2'].data_type,'n')
            book.close()
        self.assertEqual(self.client.get('/financeiro/relatorios/exportar?formato=exe').status_code,400)
        self.assertEqual(self.client.get('/financeiro/exportacoes/cadastros?conjunto=outro').status_code,400)


if __name__=='__main__':unittest.main()
