"""Contratos, parcelas e recebimentos: valores monetários em decimal."""
from datetime import datetime
from app.extensions import db


class CadastroFinanceiro(db.Model):
    __tablename__ = 'financeiro_cadastros'
    __table_args__ = (db.UniqueConstraint('tipo','nome',name='uq_financeiro_cadastro'),)
    id = db.Column(db.Integer,primary_key=True)
    tipo = db.Column(db.String(40),nullable=False,index=True)
    nome = db.Column(db.String(160),nullable=False)
    ativo = db.Column(db.Boolean,nullable=False,default=True)
    criado_por = db.Column(db.Integer,db.ForeignKey('usuarios.id'),nullable=False)
    criado_em = db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    atualizado_por = db.Column(db.Integer,db.ForeignKey('usuarios.id'))
    atualizado_em = db.Column(db.DateTime,onupdate=datetime.utcnow)


class ClienteFinanceiro(db.Model):
    __tablename__ = 'financeiro_clientes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False, index=True)
    documento = db.Column(db.String(14), unique=True)
    telefone = db.Column(db.String(40))
    email = db.Column(db.String(160))
    endereco = db.Column(db.String(240))
    observacao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    atualizado_em = db.Column(db.DateTime, onupdate=datetime.utcnow)
    contratos = db.relationship('ContratoFinanceiro', back_populates='cadastro_cliente')


class ContratoFinanceiro(db.Model):
    __tablename__ = 'financeiro_contratos'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(80), nullable=False, unique=True)
    cliente = db.Column(db.String(160), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('financeiro_clientes.id'), index=True)
    cadastro_cliente = db.relationship('ClienteFinanceiro', back_populates='contratos')
    autor = db.relationship('Usuario', foreign_keys='ContratoFinanceiro.criado_por')
    modalidade = db.Column(db.String(40), nullable=False)
    fornecedor = db.Column(db.String(160))
    forma_pagamento = db.Column(db.String(80))
    quantidade_parcelas = db.Column(db.Integer, nullable=False)
    primeiro_vencimento = db.Column(db.Date, nullable=False)
    base_mensal = db.Column(db.Numeric(14, 2), nullable=False)
    valor_total = db.Column(db.Numeric(14, 2))
    observacao = db.Column(db.Text)
    demonstracao = db.Column(db.Boolean, nullable=False, default=False)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    parcelas = db.relationship('ParcelaFinanceira', back_populates='contrato', order_by='ParcelaFinanceira.numero')

    @property
    def nome_cliente(self):
        return self.cadastro_cliente.nome if self.cadastro_cliente else self.cliente


class ParcelaFinanceira(db.Model):
    __tablename__ = 'financeiro_parcelas'
    __table_args__ = (db.UniqueConstraint('contrato_id', 'numero', name='uq_financeiro_parcela'),)
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('financeiro_contratos.id'), nullable=False, index=True)
    numero = db.Column(db.Integer, nullable=False)
    vencimento = db.Column(db.Date, nullable=False, index=True)
    previsao = db.Column(db.Numeric(14, 2), nullable=False)
    valor_real = db.Column(db.Numeric(14, 2))
    nota_kit = db.Column(db.String(80))
    observacao = db.Column(db.Text)
    versao = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {'version_id_col': versao}
    contrato = db.relationship('ContratoFinanceiro', back_populates='parcelas')
    recebimentos = db.relationship('RecebimentoFinanceiro', back_populates='parcela')


class RecebimentoFinanceiro(db.Model):
    __tablename__ = 'financeiro_recebimentos'
    __table_args__ = (db.UniqueConstraint('parcela_id', name='uq_financeiro_recebimento_integral'),)
    id = db.Column(db.Integer, primary_key=True)
    parcela_id = db.Column(db.Integer, db.ForeignKey('financeiro_parcelas.id'), nullable=False, index=True)
    valor = db.Column(db.Numeric(14, 2), nullable=False)
    data_pagamento = db.Column(db.Date, nullable=False, index=True)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    parcela = db.relationship('ParcelaFinanceira', back_populates='recebimentos')
    autor = db.relationship('Usuario', foreign_keys='RecebimentoFinanceiro.criado_por')


class EventoFinanceiro(db.Model):
    __tablename__ = 'financeiro_eventos'
    id = db.Column(db.Integer, primary_key=True)
    parcela_id = db.Column(db.Integer, db.ForeignKey('financeiro_parcelas.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    acao = db.Column(db.String(40), nullable=False)
    detalhe = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    autor = db.relationship('Usuario', foreign_keys='EventoFinanceiro.usuario_id')
