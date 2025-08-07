from flask_login import UserMixin  # Se você tiver um modelo de usuário
from datetime import datetime
from app.extensions import db
import uuid

class TokenAcessoTecnico(db.Model):
    __tablename__ = 'token_acesso_tecnico'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    tecnico = db.relationship('Tecnico', backref=db.backref('tokens_acesso', cascade='all, delete-orphan'))

# =======================
# MODELO DE TIPOS DE SERVIÇO
# =======================

class TipoServico(db.Model):
    __tablename__ = 'tipo_servico'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    empresa = db.Column(db.String(100))
    responsavel = db.Column(db.String(100))  # ← ADICIONE ESTE CAMPO
    itens = db.relationship('Item', backref='tipo_servico_rel', lazy=True)
# =======================
# MODELO DE ITENS E ESTOQUE GERAL
# =======================

class Item(db.Model):
    __tablename__ = 'itens'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(20), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'))
    valor = db.Column(db.Float, nullable=False)
    observacoes = db.Column(db.Text)
    eh_equipamento = db.Column(db.Boolean, default=False)

class Estoque(db.Model):
    __tablename__ = 'estoque'
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('tipo_servico.id', name="fk_estoque_tipo_servico"),  # Nome da FK definido
        nullable=True
    )
    responsavel = db.Column(db.String(100))  # Novo campo

    quantidade = db.Column(db.Integer, default=0)
    quantidade_minima = db.Column(db.Integer, default=0)
    endereco = db.Column(db.String(100))

    # Relacionamentos
    item = db.relationship('Item', backref='estoques')
    tipo_servico = db.relationship('TipoServico', backref='estoques')


# =======================
# NOVA FUNCIONALIDADE: REQUISIÇÕES TÉCNICOS
# =======================

class RequisicaoTecnico(db.Model):
    __tablename__ = 'requisicoes_tecnicos'
    id = db.Column(db.Integer, primary_key=True)

    # Dados do solicitante
    solicitante_responsavel = db.Column(db.String(100), nullable=False)
    solicitante_tecnico = db.Column(db.String(100), nullable=False)
    solicitante_tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'))
    tecnico_rel = db.relationship('Tecnico', foreign_keys=[solicitante_tecnico_id])

    # Tipo de serviço
    tipo_servico = db.Column(db.String(100), nullable=False)
    # Se quiser, pode usar tipo_servico_id aqui no lugar, mas precisa adaptar no restante do sistema

    # Campos adicionais
    observacao = db.Column(db.Text)
    observacao_estoque = db.Column(db.Text)
    endereco = db.Column(db.String(255))  # ✅ Novo campo
    bairro = db.Column(db.String(100))  # ✅ Novo campo
    codigo_imovel = db.Column(db.String(50))  # ✅ Novo campo
    assinatura_path = db.Column(db.String(255))
    resp_projeto = db.Column(db.String(100))

    # Status e data
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="Pendente")

    # Relacionamento com os itens
    itens = db.relationship("RequisicaoTecnicoItem", backref="requisicao", lazy=True, cascade="all, delete-orphan")

class RequisicaoTecnicoItem(db.Model):
    __tablename__ = 'requisicoes_tecnicos_itens'

    id = db.Column(db.Integer, primary_key=True)
    requisicao_id = db.Column(db.Integer, db.ForeignKey('requisicoes_tecnicos.id'), nullable=False)
    codigo = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    quantidade_estoque = db.Column(db.Integer)
    
# =======================
# NOTAS FISCAIS DE ENTRADA
# =======================

class NotaFiscalEntrada(db.Model):
    __tablename__ = 'notas_fiscais_entrada'

    id = db.Column(db.Integer, primary_key=True)
    numero_nf = db.Column(db.String(50), nullable=False)
    reserva = db.Column(db.String(50))

    # Coluna antiga (mantida para histórico)
    tipo_servico = db.Column(db.String(100))

    # Nova coluna FK (para consistência futura)
    tipo_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('tipo_servico.id', name='fk_nota_tipo_servico')
    )

    responsavel = db.Column(db.String(100))
    observacao = db.Column(db.Text)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    total_nota = db.Column(db.Float, default=0)  # ← **NOVO**

    tipo_servico_ref = db.relationship('TipoServico', backref='notas_fiscais')

    itens = db.relationship('NotaFiscalItem', backref='nota_fiscal', cascade='all, delete-orphan')

    @property
    def total_nota(self):
        """Calcula o valor total da nota somando (quantidade * valor_unitario) de todos os itens"""
        return sum(item.quantidade * item.valor_unitario for item in self.itens)

class NotaFiscalItem(db.Model):
    __tablename__ = 'notas_fiscais_itens'
    id = db.Column(db.Integer, primary_key=True)
    nota_fiscal_id = db.Column(db.Integer, db.ForeignKey('notas_fiscais_entrada.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'))
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)
    item = db.relationship('Item', backref='notas_fiscais_itens')

# =======================
# EMPRESAS PARCEIRAS
# =======================
class Empresa(db.Model):
    __tablename__ = 'empresas'
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(120), nullable=False)
    cnpj = db.Column(db.String(20), nullable=False)
    endereco = db.Column(db.String(255))
    contato = db.Column(db.String(100))
    tipo_servico = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    transferencias = db.relationship('TransferenciaExterna', back_populates='empresa', cascade='all, delete-orphan')

# =======================
# TRANSFERÊNCIA EXTERNA
# =======================

class TransferenciaExterna(db.Model):
    __tablename__ = 'transferencias_externas'
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    autorizado_por = db.Column(db.String(100), nullable=False)
    retirado_por = db.Column(db.String(100), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    empresa = db.relationship('Empresa', back_populates='transferencias')
    tipo_servico = db.relationship('TipoServico')
    itens = db.relationship('TransferenciaExternaItem', backref='transferencia', cascade='all, delete-orphan')

class TransferenciaExternaItem(db.Model):
    __tablename__ = 'transferencias_externas_itens'
    id = db.Column(db.Integer, primary_key=True)
    transferencia_id = db.Column(db.Integer, db.ForeignKey('transferencias_externas.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)

    item = db.relationship('Item')

# =======================
# TECNICOS
# =======================

class Tecnico(db.Model):
    __tablename__ = 'tecnicos'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    area_tecnica = db.Column(db.String(100))
    status = db.Column(db.String(10), default='Ativo')
    token = db.Column(db.String(100))  # ← Esse é o novo campo

    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'))
    tipo_servico_rel = db.relationship('TipoServico')

    saldos = db.relationship('SaldoTecnico', back_populates='tecnico', cascade='all, delete-orphan')  # ← Aqui está o que faltava

    def __repr__(self):
        return f"<Tecnico {self.nome} - {self.matricula}>"

# =======================
# KIT INICIAL
# =======================

class KitInicial(db.Model):
    __tablename__ = 'kits_iniciais'
    id = db.Column(db.Integer, primary_key=True)
    nome_kit = db.Column(db.String(150), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    observacao = db.Column(db.Text)
    tecnico = db.relationship('Tecnico', backref='kits_iniciais')
    tipo_servico = db.relationship('TipoServico')
    itens = db.relationship('KitInicialItem', backref='kit_inicial', cascade='all, delete-orphan')

class KitInicialItem(db.Model):
    __tablename__ = 'kits_iniciais_itens'
    id = db.Column(db.Integer, primary_key=True)
    kit_inicial_id = db.Column(db.Integer, db.ForeignKey('kits_iniciais.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)
    item = db.relationship('Item')

# =======================
# TRANSFERÊNCIA INTERNA
# =======================

class TransferenciaInterna(db.Model):
    __tablename__ = 'transferencias_internas'
    id = db.Column(db.Integer, primary_key=True)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=False)
    area_tecnica = db.Column(db.String(100), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    tecnico = db.relationship('Tecnico', backref='transferencias_internas')
    tipo_servico = db.relationship('TipoServico')
    itens = db.relationship('TransferenciaInternaItem', backref='transferencia_interna', cascade='all, delete-orphan')

class TransferenciaInternaItem(db.Model):
    __tablename__ = 'transferencias_internas_itens'
    id = db.Column(db.Integer, primary_key=True)
    transferencia_interna_id = db.Column(db.Integer, db.ForeignKey('transferencias_internas.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)
    item = db.relationship('Item')

# =======================
# USUÁRIOS DO SISTEMA
# =======================

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Ativo')

    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'))  # ← ADICIONAR ISSO
    tecnico = db.relationship('Tecnico')  # ← RELACIONAMENTO OPCIONAL

    def __repr__(self):
        return f"<Usuario {self.nome} ({self.email})>"

# =======================
# BAIXAS MANUAIS DO SALDO TÉCNICO
# =======================

class BaixaTecnica(db.Model):
    __tablename__ = 'baixas_tecnicas'
    id = db.Column(db.Integer, primary_key=True)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'), nullable=False)
    
    # Campos antigos, agora opcionais (para manter compatibilidade com dados antigos)
    endereco = db.Column(db.String(200), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    codigo_imovel = db.Column(db.String(100), nullable=True)

    # Campos usados atualmente
    responsavel = db.Column(db.String(100))
    observacao = db.Column(db.Text)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pendente")  # ✅ ESSENCIAL

    tecnico = db.relationship('Tecnico', backref='baixas_tecnicas')
    tipo_servico = db.relationship('TipoServico')
    itens = db.relationship('BaixaTecnicaItem', backref='baixa_tecnica', cascade='all, delete-orphan')




class BaixaTecnicaItem(db.Model):
    __tablename__ = 'baixas_tecnicas_itens'
    id = db.Column(db.Integer, primary_key=True)
    baixa_tecnica_id = db.Column(db.Integer, db.ForeignKey('baixas_tecnicas.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    item = db.relationship('Item')

# ✅ INVENTÁRIO TÉCNICO (deixe como está para localizar melhor)
class InventarioTecnico(db.Model):
    __tablename__ = 'inventarios_tecnicos'
    id = db.Column(db.Integer, primary_key=True)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'))
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    responsavel = db.Column(db.String(100))
    local = db.Column(db.String(100))

    tecnico = db.relationship('Tecnico', backref='inventarios')
    tipo_servico = db.relationship('TipoServico')
    itens = db.relationship('InventarioTecnicoItem', backref='inventario', cascade='all, delete-orphan')

class InventarioTecnicoItem(db.Model):
    __tablename__ = 'inventarios_tecnicos_itens'
    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(db.Integer, db.ForeignKey('inventarios_tecnicos.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'))  # corrigido aqui
    quantidade_contada = db.Column(db.Integer)

    item = db.relationship('Item')

from app import db
from datetime import datetime

class InventarioEstoque(db.Model):
    __tablename__ = 'inventario_estoque'

    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    responsavel = db.Column(db.String(100), nullable=False)

    itens = db.relationship('InventarioEstoqueItem', backref='inventario', cascade='all, delete-orphan')


class InventarioEstoqueItem(db.Model):
    __tablename__ = 'inventario_estoque_item'

    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(db.Integer, db.ForeignKey('inventario_estoque.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    quantidade_estoque = db.Column(db.Integer, nullable=False)
    quantidade_contada = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))  # Corrigido aqui

    item = db.relationship('Item')
    usuario = db.relationship('Usuario')  # Corrigido aqui


# =======================
# SALDO TÉCNICO
# =======================

class SaldoTecnico(db.Model):
    __tablename__ = 'saldo_tecnico'
    id = db.Column(db.Integer, primary_key=True)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    tipo_servico_id = db.Column(db.Integer, db.ForeignKey('tipo_servico.id'), nullable=False)
    quantidade = db.Column(db.Integer, default=0)

    endereco = db.Column(db.String(200))         # Novo campo
    bairro = db.Column(db.String(100))           # Novo campo
    codigo_imovel = db.Column(db.String(100))    # Novo campo

    tecnico = db.relationship('Tecnico', back_populates='saldos')
    item = db.relationship('Item')
    tipo_servico = db.relationship('TipoServico')

    # =======================
# CONTROLE DE FERRAMENTAS / EQUIPAMENTOS
# =======================

class EquipamentoTecnico(db.Model):
    __tablename__ = 'equipamentos_tecnicos'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=True)  # Null = está no almoxarifado
    local = db.Column(db.String(100))
    status = db.Column(db.String(20), default='almoxarifado')  # 'almoxarifado' ou 'tecnico'
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('Item')
    tecnico = db.relationship('Tecnico')

    def __repr__(self):
        return f"<EquipamentoTecnico {self.item.descricao} - {self.status}>"


class HistoricoEquipamento(db.Model):
    __tablename__ = 'historico_equipamentos'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('itens.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=True)
    local = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False)  # 'almoxarifado' ou 'tecnico'
    observacao = db.Column(db.Text)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    quantidade = db.Column(db.Integer, default=1)

    item = db.relationship('Item')
    tecnico = db.relationship('Tecnico')

    def __repr__(self):
        return f"<HistoricoEquipamento {self.item.descricao} - {self.status}>"


    



    

