"""Synthetic showcase data; never reads or modifies the operational database."""
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import mkdtemp

from app.extensions import db
from app.models import (BaixaTecnica, BaixaTecnicaItem, Empresa, Estoque, Item,
                        NotaFiscalEntrada, NotaFiscalItem, OrdemServico,
                        MovimentacaoEstoque, MovimentacaoEstoqueItem,
                        RequisicaoTecnico, SaldoTecnico, Tecnico, TipoServico, Veiculo)


def isolate_demo_database(app):
    if app.config.get('LOGISTOCK_DEMO_PUBLICO'):
        # A fresh private directory avoids reusing any existing business data.
        directory = Path(mkdtemp(prefix='logistock-public-demo-'))
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + (directory / 'demo.db').as_posix()
        app.config['SQLALCHEMY_BINDS'] = {}
        app.config['DEMO_ISOLATED_DATABASE'] = True


def seed_demo_data():
    now = datetime.utcnow()
    service = TipoServico(nome='Fibra óptica · Demonstração', tipo_estoque='empresa')
    customer = Empresa(razao_social='Cliente Exemplo · Fictício', cnpj='DEMO-CLIENTE',
                       tipo_empresa='cliente', email='cliente@example.invalid',
                       endereco='Avenida Exemplo, 100 — Cidade Fictícia',
                       observacoes='Registro fictício para demonstração pública.')
    db.session.add_all([service, customer])
    db.session.flush()
    technicians = []
    for number, name in enumerate(('Técnico Exemplo A', 'Técnica Exemplo B', 'Técnico Exemplo C'), 1):
        technician = Tecnico(nome=name, matricula=f'DEMO-{number:03}',
                             cpf=f'DEMO-CPF-{number}', email=f'tecnico{number}@example.invalid',
                             funcao='Instalação e manutenção', tipo_servico_id=service.id)
        technicians.append(technician)
        db.session.add(technician)
    db.session.flush()
    order = OrdemServico(numero_os='OS-DEMO-001', cliente_id=customer.id,
                         tipo_servico_id=service.id, endereco=customer.endereco,
                         responsavel='Responsável Exemplo', observacao='Ordem fictícia')
    db.session.add(order)
    db.session.flush()
    products = [('Cabo de fibra óptica', 'm', 2.5, 1200, 300),
                ('Conector óptico', 'un', 4.9, 18, 30),
                ('Caixa de terminação', 'un', 85.0, 40, 10),
                ('Cordão óptico', 'un', 19.9, 65, 20),
                ('Capacete de segurança', 'un', 45.0, 12, 5),
                ('Alicate de corte', 'un', 39.9, 8, 3)]
    items = []
    for number, (description, unit, price, quantity, minimum) in enumerate(products, 1):
        item = Item(codigo=f'DEMO-{number:03}', descricao=description, unidade=unit,
                    valor=price, tipo_servico_id=service.id,
                    categoria='EPI' if number == 5 else 'FERRAMENTA' if number == 6 else 'MATERIAL')
        db.session.add(item)
        db.session.flush()
        items.append(item)
        db.session.add(Estoque(item_id=item.id, tipo_servico_id=service.id,
                               quantidade=quantity, quantidade_minima=minimum,
                               valor_unitario=price, endereco=f'A-{number:02}',
                               tipo_estoque='empresa', condicao_material='novo'))
    for number in range(1, 4):
        note = NotaFiscalEntrada(numero_nf=f'NF-DEMO-{number:03}',
                                 fornecedor='Fornecedor Exemplo · Fictício',
                                 tipo_servico_id=service.id, tipo_servico=service.nome,
                                 data_hora=now - timedelta(days=number * 2),
                                 data_recebimento=(now - timedelta(days=number * 2)).date(),
                                 observacao='Documento fictício sem valor fiscal.')
        db.session.add(note)
        db.session.flush()
        for item in items[:3]:
            db.session.add(NotaFiscalItem(nota_fiscal_id=note.id, item_id=item.id,
                                          quantidade=20, valor_unitario=item.valor))
    for technician in technicians:
        db.session.add(SaldoTecnico(tecnico_id=technician.id, item_id=items[0].id,
                                    tipo_servico_id=service.id, quantidade=50,
                                    valor_unitario=items[0].valor))
    withdrawal = BaixaTecnica(tecnico_id=technicians[0].id, tipo_servico_id=service.id,
                              cliente_id=customer.id, ordem_servico_id=order.id,
                              os_cliente=order.numero_os, status='pendente',
                              endereco=customer.endereco, responsavel='Responsável Exemplo',
                              observacao='Baixa fictícia para apresentação do fluxo.')
    db.session.add(withdrawal)
    db.session.flush()
    db.session.add(BaixaTecnicaItem(baixa_tecnica_id=withdrawal.id, item_id=items[0].id,
                                   quantidade=10, valor_unitario=items[0].valor,
                                   valor_total=10 * items[0].valor))
    db.session.add(RequisicaoTecnico(solicitante_responsavel='Responsável Exemplo',
                                     solicitante_tecnico=technicians[1].nome,
                                     solicitante_tecnico_id=technicians[1].id,
                                     tipo_servico=service.nome, status='pendente',
                                     observacao='Solicitação fictícia de reposição.'))
    db.session.add(Veiculo(placa='DEMO-01', marca='Marca Exemplo', modelo='Utilitário Demonstração',
                           ano=2025, quilometragem_atual=12500,
                           responsavel=technicians[0].nome, observacao='Veículo fictício.'))
    # Material flow: supplier receipt (60 connectors), then 42 distributed.
    # Current central stock remains 18, matching the low-stock example.
    for number, technician in enumerate(technicians, 1):
        movement = MovimentacaoEstoque(
            origem_tipo='empresa', destino_tipo='tecnico', destino_id=technician.id,
            tipo_servico_id=service.id, ordem_servico_id=order.id,
            data_hora=now - timedelta(hours=number * 3),
            observacao='Distribuição fictícia de conectores para a equipe de campo.')
        db.session.add(movement)
        db.session.flush()
        db.session.add(MovimentacaoEstoqueItem(
            movimentacao_id=movement.id, item_id=items[1].id,
            quantidade=14, valor_unitario=items[1].valor, condicao_material='novo'))
        db.session.add(SaldoTecnico(tecnico_id=technician.id, item_id=items[1].id,
                                    tipo_servico_id=service.id, quantidade=14,
                                    valor_unitario=items[1].valor))
    db.session.commit()
